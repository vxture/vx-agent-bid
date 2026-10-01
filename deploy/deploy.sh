#!/usr/bin/env bash
# GENERATED_BY_AI
# MODEL: claude-opus-5
# DATE: 2026-09-10
#
# 宿主机上的部署生命周期。由 CI（deploy.yml / rollback.yml）在镜像构建之后
# 通过 SSH 调用，也可以在主机上手工跑。
#
#   bash deploy/deploy.sh all      # 目录 → 拉镜像 → 起栈 → 验证 → 清旧镜像
#   bash deploy/deploy.sh start    # 只拉 + 修 private/ 属主 + 起
#   bash deploy/deploy.sh owner    # 只修 private/ 属主（uid 取自 api 镜像）
#   bash deploy/deploy.sh pin      # 只把 IMAGE_* 对应的镜像钉进 docker-compose.override.yml
#   bash deploy/deploy.sh verify   # 只验证
#   bash deploy/deploy.sh prune    # 只清旧镜像
#
# 与基准产品 vxtpl 的三处形态差异，每一处都改变这个脚本的形状：
#
#   1. **三个镜像**（api / ai / web），api 与 worker 共用 api 那一个。
#      三者必须同 tag——CI 侧已经保证同批构建，这里再断言一次，
#      因为「拉到两新一旧」的表现是前端调一个后端还没有的接口拿 404，
#      两侧都不会说版本不匹配。
#   2. **两个有状态服务**（PostgreSQL 与 Temporal），外加一次性的 temporal-db-init。
#      `up -d` 必须让 compose 按 depends_on 的健康条件排序，不能并发糊上去。
#   3. **验证要探三个**，不是一个。只探 api 的话，ai 挂了在界面上表现为
#      「点了没反应」，而部署会报成功。
#
# 镜像 tag 与 registry 全部来自 CI 导出的环境变量：
#   IMAGE_REGISTRY / IMAGE_NAMESPACE / IMAGE_TAG（主源 = GHCR）
#   FALLBACK_IMAGE_REGISTRY / FALLBACK_IMAGE_NAMESPACE（备源 = 阿里云 ACR）

set -euo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$REPO_DIR"

PRODUCT_CODE="${PRODUCT_CODE:-tenderforge}"

# 三个镜像名。api 与 worker 共用第一个——它们是同一个镜像的两种启动形态。
IMAGES=("${PRODUCT_CODE}-api" "${PRODUCT_CODE}-ai" "${PRODUCT_CODE}-web")

# 容器内口。**字面量**，与端口登记表和 compose 的 healthcheck 一致。
#
# 这里刻意不从环境读：`verify` 用 `docker exec` 进容器探，所以要紧的是容器
# 内那一侧的口，而 CI 并不导出它。曾经从环境读的版本会在 CI 未导出时悄悄
# 回落到默认值，于是健康检查探一个没人在听的口，而容器早已 healthy——
# 报出来的是「验证失败」，真实情况是「探错了地方」。常量不会和自己不一致。
API_CONTAINER_PORT=8081
AI_CONTAINER_PORT=8000

# 宿主机发布口，只用于日志。端口登记表 2026-09-10 分配 4050（L3 #5）。
# 它与边缘 nginx 的 upstream 不一致正是整条链唯一真正会坏的地方，
# 所以打印出来，而不是留给运维去推断。
published_port() {
  grep -E '^\s*APP_PUBLISH_PORT\s*=' "$REPO_DIR/.env" 2>/dev/null \
    | tail -1 | grep -oE '[0-9]+' | tail -1 || true
}

# 持久数据的位置。**compose 里的两个挂载点都 bind 到这里**，不是具名卷——
# 具名卷落在 /var/lib/docker/volumes（系统盘），而这台机器的持久化位置是
# md0 阵列上的 <stack_root>/data。用具名卷的表现不是报错，是数据默默写到了
# 错误的盘上，直到系统盘满或换机时才发现。
#
# 它在 REPO_DIR **里面**，rsync 那一步用 --exclude='data' 把它排除在
# --delete 之外——容器写出来的数据是 root 所有，让 rsync 碰它会在下一次
# 部署时以权限错误失败，而那个错误信息离原因很远。
#
# 显式给，不从 REPO_DIR 推导。推导版本（dirname $REPO_DIR）在 REPO_DIR 是
# /srv/md0/tenderforge 时会指向 /srv/md0/data——那是所有产品共用的一层，
# 两个产品的数据会落进同一个目录，而且不会有任何报错。
DATA_DIR="${DATA_DIR:-$REPO_DIR/data}"
export DATA_DIR

log() { echo "[deploy] $*"; }

compose() { docker compose --project-directory "$REPO_DIR" "$@"; }

cmd_environment() {
  test -f "$REPO_DIR/.env" || { log "FATAL: 缺少 $REPO_DIR/.env"; exit 1; }
  # DEPLOY_STAGE 在 compose 里是 ${DEPLOY_STAGE:?}，缺了 compose 自己会拒绝；
  # 这里提前报，是为了让错误出现在「部署脚本」而不是「compose 语法」那一层。
  grep -qE '^\s*DEPLOY_STAGE\s*=\s*\S' "$REPO_DIR/.env" || {
    log "FATAL: .env 里没有 DEPLOY_STAGE。缺省会让四条平台通道静默走替身。"
    exit 1
  }
  log "环境就绪（发布口 $(published_port)，容器内 api:${API_CONTAINER_PORT} ai:${AI_CONTAINER_PORT}）"
}

cmd_directories() {
  # 两个子目录对应 compose 里的两个 bind mount。少建一个的表现是
  # Docker 替你建一个 root 所有的空目录——容器起得来，但 postgres 会因为
  # 目录属主不对而拒绝初始化。
  mkdir -p "$DATA_DIR/postgres" "$DATA_DIR/private"
  log "数据目录就位：$DATA_DIR（postgres / private）"
}

# private/ 的属主必须是 api 镜像里的运行用户（api 与 worker 共用这个镜像）。
#
# 2026-09-14 生产上撞过：cmd_directories 以部署用户（uid 1000）建出 private/，
# 容器以镜像里的 app（uid 10001）运行，目录 775——能读不能写。服务照常 healthy、
# 部署照常报绿，直到第一次有人上传招标文件才报 AccessDeniedException。
#
# uid **从镜像里读**，不写死：Dockerfile 的 useradd 才是它的唯一来源，这里再写一份
# 10001，就是 Dockerfile 改了之后悄悄过期的那一份。
#
# chown 借同一个镜像以 root 做：部署用户不是 root、不保证有 sudo，但它必然能跑
# docker（整个脚本都靠它）。用 api 镜像而不是另拉一个工具镜像——它刚拉下来、
# tag 钉死，不给部署多引入一个镜像源依赖。
#
# **不递归**：目录里的东西都是容器自己写的，属主本来就对；递归 chown 会让每次部署
# 的耗时随招标原件与导出文件的数量增长。
#
# postgres/ 不需要这一步：postgres 镜像的入口脚本以 root 启动时自己修数据目录属主。
ensure_private_owner() {
  local image="${IMAGE_REGISTRY:-ghcr.io}/${IMAGE_NAMESPACE:-vxture}/${PRODUCT_CODE}-api:${IMAGE_TAG:-local}"
  local dir="$DATA_DIR/private" want have
  # start 可以不经 directories 单独跑；那时目录缺失，交给 compose 建出来的是 root 的。
  mkdir -p "$dir"
  want="$(docker run --rm --entrypoint id "$image" -u)" || {
    log "FATAL: 无法从 ${image} 读出运行用户 uid"
    exit 1
  }
  case "$want" in
    '' | *[!0-9]*)
      log "FATAL: 从 ${image} 读到的 uid 不是数字：'${want}'"
      exit 1
      ;;
  esac
  have="$(stat -c %u "$dir")"
  if [ "$have" = "$want" ]; then
    log "private/ 属主已是 uid ${want}，跳过"
    return 0
  fi
  docker run --rm --user 0 --entrypoint chown -v "$dir:/target" "$image" "$want" /target
  # 修完再读一次：chown 返回 0 不等于这个目录的属主真的变了。
  have="$(stat -c %u "$dir")"
  if [ "$have" != "$want" ]; then
    log "FATAL: private/ 属主修正后仍是 uid ${have}，期望 ${want}"
    exit 1
  fi
  log "private/ 属主已修正为 uid ${want}（取自 ${image} 的运行用户）"
}

# 拉一个镜像：主源失败就走备源，并把备源打上主源的名字，
# 这样 compose 里的镜像引用不需要知道自己是从哪拉来的。
pull_one() {
  local image="$1" tag="$2"
  local reg="${IMAGE_REGISTRY:-ghcr.io}" ns="${IMAGE_NAMESPACE:-vxture}"
  local primary="${reg}/${ns}/${image}:${tag}"
  log "拉取 ${primary}"
  if docker pull "$primary"; then return 0; fi

  local fb_reg="${FALLBACK_IMAGE_REGISTRY:-}" fb_ns="${FALLBACK_IMAGE_NAMESPACE:-}"
  if [ -z "$fb_reg" ] || [ -z "$fb_ns" ]; then
    log "FATAL: 主源拉取失败且没有配置备源"
    exit 1
  fi
  local fallback="${fb_reg}/${fb_ns}/${image}:${tag}"
  log "主源失败，改用备源 ${fallback}"
  # 显式 return，不靠 set -e：重试时 pull_one 在 `( … ) || rc=1` 里跑，bash 在 || 左边
  # 关闭 errexit——靠 set -e 的话，备源也拉不到时它会接着 tag 并返回 0，
  # 一个真的拉不到的镜像会被当成拉到了。
  docker pull "$fallback" || return 1
  docker tag "$fallback" "$primary" || return 1
}

# 把本次部署的镜像引用钉进 docker-compose.override.yml（compose 自动合并它）。
#
# 为什么需要：compose 里的镜像是 ${IMAGE_REGISTRY}/${IMAGE_NAMESPACE}/…:${IMAGE_TAG}，
# 这三个变量只在 CI 部署时导出，宿主机 .env 里没有。2026-09-15 在主机上手工
# `docker compose up -d api` 改一个环境变量，镜像被解析成
# ghcr.io/vxture/tenderforge-api:local：拉取被拒，转去本地构建，再因主机上没有源码
# 而失败。更坏的结局是主机上恰好有个 :local 镜像，服务被悄悄换成它。
#
# 为什么是 override 而不是写进 .env：.env 是运维的权威文件，部署从不覆盖它
# （见 deploy.yml 的 bootstrap 注释）；让部署改写它，等于每次发布都去动运维的配置。
# override 由部署独占生成，deploy.yml / rollback.yml 的 rsync --delete 排除它——
# 一次倒在拉取阶段的部署不会把上一次的钉子删掉。
#
# 引用写**主源名**：备源回落时 pull_one 已经把镜像打回主源名，本地一定有。
# 必须在拉取全部成功之后写（钉一个本地没有的引用，手工 up 会去拉），并在 up 之前写
# （up 与之后每一次手工操作读到的是同一组引用）。
# scripts/guardrails/check_deploy_image_pins.py 对着真实的 `docker compose config` 验它。
write_image_pins() {
  local tag="${IMAGE_TAG:-local}"
  local prefix="${IMAGE_REGISTRY:-ghcr.io}/${IMAGE_NAMESPACE:-vxture}/${PRODUCT_CODE}"
  local target="$REPO_DIR/docker-compose.override.yml" tmp
  # 同目录临时文件 + mv：写到一半被打断时，compose 读到的要么是旧钉子要么是新钉子，
  # 不会是半个 YAML。
  tmp="$(mktemp "$REPO_DIR/.docker-compose.override.XXXXXX")"
  cat > "$tmp" <<EOF
# 由 deploy/deploy.sh 在每次部署时生成——不入仓，不要手改。
# 让宿主机上手工执行的 docker compose 解析到本次部署的镜像，而不是 :local。
services:
  api:
    image: ${prefix}-api:${tag}
  worker:
    image: ${prefix}-api:${tag}
  ai:
    image: ${prefix}-ai:${tag}
  web:
    image: ${prefix}-web:${tag}
EOF
  chmod 644 "$tmp"
  mv "$tmp" "$target"
  log "镜像已钉入 docker-compose.override.yml（${prefix}-*:${tag}）"
}

cmd_start() {
  local tag="${IMAGE_TAG:-local}"
  test -n "$tag"

  # 三个镜像**同一个 tag**。这不是约定，是断言：CI 侧同批构建，这里再确认
  # 一次，因为一旦拉到两新一旧，故障表现会离原因很远。
  # **三个并行拉**。串行时总时长是三者之和，而三个镜像大小差一个数量级
  # （ai 约 1.5GB，web 约 50MB），串行等于让最小的那个排在最大的后面干等。
  # 各自的输出收进独立文件再顺序打印——并行的日志交织在一起，出问题时分不清
  # 哪一行属于哪个镜像。
  local pids=() logs=() failed=() rc=0 i=0
  for image in "${IMAGES[@]}"; do
    logs[i]="$(mktemp)"
    pull_one "$image" "$tag" > "${logs[i]}" 2>&1 &
    pids[i]=$!
    i=$((i + 1))
  done
  i=0
  for image in "${IMAGES[@]}"; do
    wait "${pids[i]}" || failed+=("$image")
    cat "${logs[i]}"
    rm -f "${logs[i]}"
    i=$((i + 1))
  done
  # 并行失败的**逐个**再拉一次。本机是 Docker 29 + containerd 镜像存储：几个镜像共享层时
  # 同时拉，会撞上 containerd 的
  #   failed commit on ref "layer-sha256:…": rename …/ingest/…/data …: no such file or directory
  # ——同一层的 ingest 文件被另一个拉取先挪走了（2026-09-30 v0.1.23、2026-10-01 v0.1.27
  # 两次，都在 ACR 认证抖动、三个镜像一起转去备源时出现）。它是并发竞争，串行重拉即可；
  # 一切顺利时仍然并行，快的那条不变。子 shell：pull_one 缺备源配置时会 exit。
  if [ "${#failed[@]}" -gt 0 ]; then
    log "并行拉取有 ${#failed[@]} 个失败（${failed[*]}），逐个重试一次"
    for image in "${failed[@]}"; do
      ( pull_one "$image" "$tag" ) || rc=1
    done
  fi
  [ "$rc" -eq 0 ] || { log "FATAL: 有镜像拉取失败（并行与逐个重试都未成功），见上面各自的日志"; exit 1; }

  # 拉取全部成功才钉，且赶在 up 之前——理由见 write_image_pins。
  write_image_pins

  # 第三方镜像（Postgres / Temporal / temporal-ui）单独拉，失败不致命：
  # 它们的 tag 是钉死的，本地多半已经有，而拉不到时 `up -d` 会用本地那份。
  #
  # **服务名必须存在。** 这里一度写着 `mysql`——库层迁到 Postgres 之后没跟着改。
  # compose 遇到未知服务会让整条命令失败，而末尾的 `|| true` 把它咽掉，于是
  # 三个第三方镜像一个都没被预拉；等到 `up -d` 阶段才去拉，任何一次镜像源抖动
  # 都会直接拖垮整次部署，而日志里只看得到那一次拉取失败。
  compose pull db temporal temporal-ui || true

  # 必须在拉镜像之后（uid 从 api 镜像里读）、在 up 之前（容器一起来就要写 private/）。
  ensure_private_owner

  # depends_on 里带 condition: service_healthy，所以 compose 会自己排序：
  # db → temporal-db-init（一次性）→ temporal → api → worker/web。
  # 不要在这里手动分批起——那等于把顺序写第二遍，而两份顺序迟早会分叉。
  if ! compose up -d; then
    dump_failure_context
    return 1
  fi
  log "已启动（tag=${tag}）"
}

# `up -d` 失败时，把现场打进 CI 日志。
#
# 不这么做的代价已经付过一次：一次部署倒在 `dependency failed to start:
# container ... is unhealthy`，CI 日志里就这一句。真正的原因（Temporal 的角色
# 缺 CREATEDB，auto-setup 在建 visibility 库时被拒后退出）是在本地重搭一套
# Postgres + auto-setup 才看见的。**容器日志留在主机上，而排查的人在 CI 里**，
# 这中间隔着一次 SSH，也就隔着一次「先去申请权限」。
dump_failure_context() {
  log "!! 启动失败，下面是现场"
  # **必须带 -a**：compose ps 默认只列运行中的容器，而一次性初始化容器
  # （temporal-db-init）跑完就退出，恰恰是最需要看日志的那个。少了这个 -a，
  # 上一次排查白跑了一轮——现场转储把唯一有用的那份日志漏掉了。
  compose ps -a || true

  # **默认打印，只在确认健康时才跳过。**
  #
  # 上一版反过来：默认跳过，只在状态匹配到某几个值时才打。它漏掉了崩溃重启的
  # api——`Restarting` 的容器状态在 running 与 restarting 之间来回跳，判断恰好
  # 撞上那一瞬的 running 就被跳过了。于是三个正常容器的日志都打了，唯独那个
  # 真正出问题的没有。
  #
  # 方向反过来之后，一次竞态最多让日志多打几屏，不会让它消失。诊断信息宁可冗余，
  # 不能缺失——缺失的代价上一轮量过：一次本地重搭复现。
  #
  # 判据用 Status 而不是 State：Status 里带健康信息（`Up 3 minutes (healthy)` /
  # `Restarting (1)` / `Exited (0)`），而 State 只有一个词，分不出健康与否。
  local svc status
  for svc in $(compose config --services 2>/dev/null); do
    status="$(compose ps -a --format '{{.Status}}' "$svc" 2>/dev/null | head -1)"
    # 判据表（Status 的真实形态，逐条验过）：
    #   Up 3 minutes (healthy)          跳过——健康
    #   Up 5 minutes                    跳过——没有健康检查的服务，稳定运行
    #   Up 10 seconds (health: starting) 打印——失败那刻还没起来的，正是可疑的那个
    #   Up 2 seconds (unhealthy)        打印
    #   Restarting (1) 2 seconds ago    打印（不以 Up 开头，落最后一支）
    #   Exited (0) / Created / Dead / 空 打印
    case "$status" in
      *"(healthy)"*) continue ;;
      # 带健康信息但不是 healthy：starting 与 unhealthy 都要看。
      Up*"("*) ;;
      Up*) continue ;;
      # 取不到状态也打：宁可多打，不可漏掉。
      *) ;;
    esac
    log "--- $svc（${status:-状态未知}）最后 80 行 ---"
    compose logs --no-color --tail=80 "$svc" 2>&1 || true
  done
}

# 探一个容器内的 liveness 端点。
# 探的是 **liveness**（零依赖）而不是 readiness：这一步回答的是「新镜像跑起来
# 了吗」，依赖没就绪是另一个问题，混在一起会让一次数据库慢启动被报成部署失败。
probe() {
  local service="$1" port="$2" path="$3" tool="$4"
  case "$tool" in
    curl)   compose exec -T "$service" curl -fsS "http://127.0.0.1:${port}${path}" >/dev/null 2>&1 ;;
    python) compose exec -T "$service" python -c \
              "import urllib.request;urllib.request.urlopen('http://127.0.0.1:${port}${path}')" >/dev/null 2>&1 ;;
    wget)   compose exec -T "$service" wget -q --spider "http://127.0.0.1:${port}${path}" >/dev/null 2>&1 ;;
    # 没有默认分支时，未知的 tool 会让 case 什么都不做并返回 0——
    # 于是 probe 报成功、verify 判定通过，而<b>一次探测都没发生</b>。
    # 这是这个脚本里最坏的一种失败：部署报绿，服务其实没起来。
    *)      log "FATAL: probe 不认识的探测工具 '$tool'"; return 1 ;;
  esac
}

cmd_verify() {
  local tries=0 ok_api=false ok_ai=false ok_web=false
  # 60 次 × 3 秒 = 3 分钟。Java 冷启动在这台机器上要一分多钟，
  # vxtpl 那边的 20 次（1 分钟）对本产品不够——超时的表现会是「部署失败」，
  # 而实际只是还没起完。
  until [ "$tries" -ge 60 ]; do
    $ok_api || { probe api "$API_CONTAINER_PORT" /api/health curl && ok_api=true; }
    $ok_ai  || { probe ai  "$AI_CONTAINER_PORT"  /health     python && ok_ai=true; }
    $ok_web || { probe web 80 / wget && ok_web=true; }
    if $ok_api && $ok_ai && $ok_web; then
      log "验证通过：api / ai / web 三个存活端点全部应答（发布口 $(published_port)）"
      # 把身份块打出来。部署后核对 version/gitSha/stage 是真值而不是
      # dev/unknown/local，是规范 025 §7 合规清单的第 5 条——
      # 「部署成功」和「部署了正确的东西」是两件事。
      compose exec -T api curl -fsS "http://127.0.0.1:${API_CONTAINER_PORT}/api/health" || true
      echo
      return 0
    fi
    tries=$((tries + 1))
    sleep 3
  done

  log "验证失败：api=${ok_api} ai=${ok_ai} web=${ok_web}"
  compose ps
  # 只打没通过的那个的日志。全打会把真正的那几行淹掉。
  $ok_api || compose logs --tail 60 api
  $ok_ai  || compose logs --tail 60 ai
  $ok_web || compose logs --tail 60 web
  exit 1
}

cmd_prune() {
  # 只保留正在跑的那几个镜像。三个镜像每个 tag 一份，累积得比 vxtpl 快三倍。
  # 放在 verify 之后跑（见 cmd_all），所以验证失败的那次不会清任何东西——
  # 那时候旧镜像正是回滚要用的东西。
  local keep=() id pruned=0
  for container in "${PRODUCT_CODE}-api" "${PRODUCT_CODE}-ai" "${PRODUCT_CODE}-web"; do
    id="$(docker inspect --format '{{.Image}}' "$container" 2>/dev/null || true)"
    [ -n "$id" ] && keep+=("$id")
  done
  if [ "${#keep[@]}" -eq 0 ]; then
    log "prune 跳过（没有在跑的容器）"
    return 0
  fi

  local ref
  while IFS= read -r ref; do
    [ -n "$ref" ] || continue
    id="$(docker image inspect --format '{{.Id}}' "$ref" 2>/dev/null || true)"
    [ -n "$id" ] || continue
    local keeping=false
    for kept in "${keep[@]}"; do [ "$id" = "$kept" ] && keeping=true; done
    $keeping && continue
    if docker rmi "$ref" >/dev/null 2>&1; then
      pruned=$((pruned + 1))
      log "清掉 ${ref}"
    fi
  done < <(docker images --format '{{.Repository}}:{{.Tag}}' \
           | grep -E "/(${PRODUCT_CODE}-(api|ai|web)):" || true)
  log "镜像 prune 完成（清掉 ${pruned} 个，保留在跑的三个）"
  prune_volumes
}

# 清掉本栈自己产生的、没有任何容器引用的 Docker 卷。
#
# **数据不在这些卷里。** 两个持久化位置都是 bind mount，指向 $DATA_DIR 下的
# postgres/ 与 private/——bind mount 不是 Docker 卷，`volume prune` 从构造上
# 就碰不到它们。这是一个结构性的安全性质，比"小心不要删错"强得多。
#
# 所以这里不设一串"动手前先检查"的守卫，而是**断言让这件事安全的那个不变量**：
# 两个 bind 目录必须存在。它们不存在，说明数据要么还没建、要么已经被改回具名卷
# ——两种情况下"prune 碰不到数据"这句话都不再成立，此时宁可跳过。
#
# 这段的第一版走的是另一条路：具名卷 + 三道运行时守卫。撞出的两件事留在这里，
# 因为它们与"卷放哪"无关，换成 bind mount 之后仍然成立：
#   * 停止的容器**仍然持有卷引用**，prune 碰不到它的卷；容器被移除（compose down）
#     之后才失去引用。实测：down 之后对具名卷 prune，40.89MB 数据一次没了。
#   * **Docker 23+ 起 `volume prune` 默认只删匿名卷**，具名的要 `--all`。
#     不加的表现是永远「reclaimed 0B」——看起来在跑，实际什么都没做。
prune_volumes() {
  local dir
  for dir in "$DATA_DIR/postgres" "$DATA_DIR/private"; do
    if [ ! -d "$dir" ]; then
      log "卷 prune 跳过：$dir 不存在。"
      log "  持久数据应当在 bind mount 上（prune 碰不到）；它不在，说明前提变了。"
      return 0
    fi
  done

  # --all：见上面第二条。--filter：把范围限死在本栈自己的卷上，
  # 不碰同机其它产品的。prune 本身只删没有容器引用的卷。
  local reclaimed
  reclaimed="$(docker volume prune -f --all     --filter "label=com.docker.compose.project=${PRODUCT_CODE}" 2>&1     | grep -i "reclaimed" || true)"
  log "卷 prune 完成（${reclaimed:-无可回收}）"
}

cmd_all() {
  cmd_environment
  cmd_directories
  cmd_start
  cmd_verify
  cmd_prune
}

case "${1:-}" in
  all)         cmd_all ;;
  environment) cmd_environment ;;
  directories) cmd_directories ;;
  owner)       ensure_private_owner ;;
  pin)         write_image_pins ;;
  start)       cmd_start ;;
  verify)      cmd_verify ;;
  prune)       cmd_prune ;;
  *) echo "usage: bash deploy/deploy.sh {all|environment|directories|owner|pin|start|verify|prune}"; exit 1 ;;
esac
