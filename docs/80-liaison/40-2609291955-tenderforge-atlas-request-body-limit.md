# 联络函：`/v1/chat` 的请求体上限是 100 KB，招标文件解读在网关入口被拒

- Stamp: 2609291955（2026-09-29 19:55）
- From: tenderforge 线
- To: Atlas 线（抄送平台线）
- Status: request（需要 Atlas 侧改配置）
- 引用：[30-2609142131](./30-2609142131-tenderforge-atlas-generic-routes.md)（各路由的模型下限）

## 一句话

Atlas 的 JSON 请求体上限目前是 **102,400 字节（100 KB）**，看上去是 Express/Nest 的 JSON 解析
中间件（body-parser）的出厂默认值。本产品一次真实的招标文件解读请求是 **120,507 字节**，在网关入口就被拒了，
没有到达路由、授权和模型，**解读、目录、正文、审查四个环节里至少三个会稳定撞上这个上限**。
请把 `/v1/chat` 的请求体上限提到 **10 MB**，并请同时处理下面第 2–4 条，那几条决定下一次
撞到限制时双方能不能在一分钟内看懂。

## 发生了什么（2026-09-29 生产）

- 本产品 v0.1.21，路由与授权均正常：同一时刻系统验证页的 Atlas 活体探测对
  `chat/default` · `chat/deterministic` · `chat/fast` · `chat/reasoning` **4/4 走通**
  （探测只发 `ping`，请求体几百字节）。
- 用户上传一份招标文件发起解读。第一步 `project_overview_source_selection`（路由 `chat/deterministic`）
  两次尝试都在 **40–60 ms** 内失败。
- `vx-atlas-app-prod` 同一时刻的日志：

```
[Nest] 1  - 09/29/2026, 11:21:53 AM   ERROR [ExceptionsHandler] PayloadTooLargeError: request entity too large
    at readStream (/app/dist/main.cjs:31979:21)
    at getRawBody (/app/dist/main.cjs:31960:16)
    at read (/app/dist/main.cjs:42166:7)
    at jsonParser (/app/dist/main.cjs:42280:9)
    ...
  expected: 120507,
  length: 120507,
  limit: 102400,
  type: 'entity.too.large'
}
[Nest] 1  - 09/29/2026, 11:22:04 AM   ERROR [ExceptionsHandler] PayloadTooLargeError: request entity too large
  (同上，length: 120507, limit: 102400)
```

两点值得 Atlas 侧注意：

1. **错误是在 `jsonParser` 里抛出的**：请求没有进入路由，也就没有 `requestId` 落库、没有计量记录，
   Atlas 的请求日志里查不到这两笔，只在进程日志里有。
2. **它走的是 `[ExceptionsHandler]`，即未处理异常的兜底路径**，而不是 X-1 封套。从产品侧看，
   这次失败没有 `code`，我们只能记为通用的 `AI_PROVIDER_ERROR`，界面上是一句「AI 工作流执行失败」。
   从拿到这句提示到定位出原因，靠的是直接读 Atlas 的进程日志。

## 为什么 100 KB 对一个模型网关不够

本产品发出的请求体中，中文按 UTF-8 **每字 3 字节**计（实测 httpx 0.28 编码为 3.02 字节/字，
不做 `\u` 转义）；另有 JSON Schema 与提示词的固定开销，每次约 5–15 KB。按产品代码里的上限估算：

| 环节 | 路由 | 输入规模上限（产品代码） | 请求体估算 | 对 100 KB |
| --- | --- | --- | --- | --- |
| 解读·概述选段 `project_overview_source_selection` | `chat/deterministic` | **整份招标文件**（本产品侧的问题，见下文「产品侧的承诺」） | 本次实测 **120,507 B**；300 页招标文件约 0.9 MB | ❌ |
| 解读·概述成文 `project_overview_extraction` | `chat/deterministic` | 选中原文 ≤ 48,000 字 | 约 150 KB | ❌ |
| 解读·评分排序 `technical_scoring_extraction` | `chat/deterministic` | 仅条款目录 | 通常 < 60 KB | ✅（随评分表长度增长） |
| 目录 `outline_*` / `bid_strategy_planning` | `chat/default` / `chat/reasoning` | 参考素材 ≤ 50,000 字 + 评分与概述 | 约 160–200 KB | ❌ |
| 正文 `chapter_drafting` | `chat/fast` | 参考 8,000 + 方案约束 16,000 + 概述/评分/前文/承诺约 10,000 字 | 约 100–120 KB | ❌（临界） |
| 局部修订 `section_revision` | `chat/default` | 选区与上下文 | 通常 < 60 KB | ✅ |
| 全文审查 `consistency_review` | `chat/reasoning` | **全部章节摘录，每章 ≤ 16,000 字** | 200 页标书约 0.6 MB；500 页约 1.5 MB | ❌ |

也就是说，**100 KB 只够最短的两个环节**，而本产品的主流程里正文续写的调用次数占绝大多数，
正好卡在临界线上：会出现「同一份标书，有的章节能写、有的章节写不了」的随机失败，
那是最难排查的一种。

作为对照：主流模型 API 的单次请求上限都在 MB 级（例如 Anthropic Messages API 为 32 MB）。
模型网关的请求体上限应当由它所挂模型的上下文窗口决定，而不是由 HTTP 框架的默认值决定。
按 30 号函里 `chat/reasoning` 要求的 256K 上下文折算，中文满窗约 0.6–0.8 MB；
10 MB 留出了多轮消息、工具调用与后续多模态（`chat/vision`）的余量。

## 请求 Atlas 线处理的事项

按优先级：

### 1. 【阻断】`/v1/chat` 的 JSON 请求体上限提到 10 MB

- Nest 下通常是 `app.useBodyParser('json', { limit: '10mb' })`，或在自建的 `express.json()` 上加 `limit`。
  以 Atlas 实际的启动代码为准。
- **请顺带检查整条链路上的其它上限**，只改应用层可能不够：
  - Atlas 前面若有反向代理（nginx 的 `client_max_body_size` **默认 1 MB**、网关/负载均衡的请求体限制）；
  - Atlas 调上游模型供应商时的请求体上限；
  - 同一进程里 `/v1/embed` 等其它接口的 `urlencoded` 解析器是否有独立的上限（`embedding/*` 与 `rerank/*`
    已授权给本产品，后续会用于招标原文与范文的召回，单批输入同样可能超过 100 KB）。
- 如果 Atlas 对「单请求多大」有成本或安全上的顾虑，请直接告诉我们上限是多少，
  产品侧会按那个数设计分片。我们要的是**一个明确的数**，大小可以商量。

### 2. 请求体超限时返回 X-1 封套，而不是走未处理异常

期望形状：

```json
HTTP 413
{ "code": "PAYLOAD_TOO_LARGE", "message": "request body 120507 bytes exceeds limit 10485760", "retryable": false }
```

- 为什么要 `retryable:false`：同一份请求重发多少次都一样大。当前走 `ExceptionsHandler` 时，
  产品侧拿不到 `code`，只能按状态码猜要不要重试；猜错了就是对一个注定失败的请求白白重试。
- 为什么要在 `message` 里写上实际大小和上限：这两个数就是排查所需的全部信息，
  有了它们，产品侧的错误提示可以直接告诉用户「这份文件太大，已按分段处理」，而不是「AI 工作流执行失败」。

### 3. 输入超出所路由模型的上下文窗口时，返回结构化码

请求体上限放开之后，下一个会撞到的是模型上下文窗口，而那个错误来自上游供应商，
各家说法不一，读起来往往不像「上下文不够」（30 号函「怎么确认配对了」一节已提过这个担心）。
请在网关侧按路由实际挂的模型预估 token 数，超出时返回：

```json
HTTP 400
{ "code": "CONTEXT_LENGTH_EXCEEDED", "message": "…", "retryable": false,
  "details": { "endpointCode": "chat/reasoning", "modelCode": "…", "inputTokens": 301234, "contextWindow": 262144 } }
```

若 endpoint 配了长上下文的备选模型，**先在网关内尝试备选**，都放不下再返回这个码。
产品侧收到它就会走分片路径；网关**不要**替产品静默截断——删哪一段是业务判断，
截断后的输入模型照样会答，只是答错，而且没有任何报错。

### 4. 在 `/v1/models`（或 `/v1/endpoints`）公开每条路由的容量

产品侧的分片预算需要这两个数，目前只能按 30 号函里自己提的下限去猜：

| 字段 | 用途 |
| --- | --- |
| `contextWindow`（token） | 产品按它给每次调用定输入预算 |
| `maxOutputTokens` | 目录骨架这类长输出环节据此判断会不会截断 |
| `maxRequestBytes` | 即第 1 条的上限；公开出来，产品侧出站前就能自查 |

按**路由**给而不是只按模型给：产品只认 `endpointCode`，不知道也不该知道背后挂的是哪个模型；
运营改了指向，这几个数随之变化，产品不需要发版。

### 5. 【顺带】请核对 30 号函的模型下限

30 号函请 Atlas 核对四条路由所挂模型的上下文与输出下限（`chat/reasoning` ≥ 128K、500 页标书需 256K 等），
这件事目前还没有回音。第 1 条放开后，这些下限就是下一道实际约束。

## 产品侧的承诺（不是把问题全推给网关）

放开上限之后，本产品也不会把「输入可以无限大」当成前提。以下几项由本产品在自己仓内完成，不需要 Atlas 配合：

1. **概述选段改为分窗口**：本次失败的第一步目前是把整份招标文件一次送去挑片段，输入随文件长度无上限增长。
   改为按固定大小切窗口、各窗口独立挑选、合并后按原文顺序封顶，单次请求有确定的上限，与文件页数无关。
2. **全文审查改为有界输入**：目前按章节全文摘录一起送入，随标书规模线性增长；改为分批审查或基于章节摘要审查，
   使单次请求有上限。
3. **出站前预算自查**：每次调用前在产品侧估算请求体与 token，超出预算时在本地报出「哪个环节、多大、上限多少」，
   不再等网关拒绝。第 4 条公开的数到位后，预算直接取自 Atlas。
4. **透出 Atlas 的错误码**：本产品此前把 Atlas 返回的 `code` 与 `message` 吞成了一句通用提示，
   本次定位因此必须读 Atlas 的进程日志。改为原样记入失败记录并显示在界面上。

即便如此，第 1 条仍然是阻断项：上表里「概述成文」「目录」「正文」这些**本来就有上限**的环节，
上限本身就已经超过 100 KB。

## 怎么验证

Atlas 侧改完后可以自行复现与回归：

```bash
# 构造一个约 2 MB 的合法请求体（中文），期望 200 或业务错误码，而不是 413 / 500
python3 - <<'PY' > /tmp/big.json
import json
text = "招标文件正文" * 120_000          # 约 72 万字，≈ 2.1 MB
print(json.dumps({"endpointCode": "chat/fast", "taskId": "atlas-body-limit-check",
                  "messages": [{"role": "user", "content": text[:1000]}],
                  "padding": text}, ensure_ascii=False))
PY
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://<atlas>/v1/chat \
  -H "Authorization: Bearer <S2S 票>" -H "Content-Type: application/json" --data-binary @/tmp/big.json
```

- `padding` 这个未知字段只用来撑大体积：真正送给模型的只有 `messages` 里的 1,000 字，
  请求若通过会产生一次很小的模型调用。若 Atlas 对未知字段做严格校验而答 400，
  也足以证明请求已越过 `jsonParser`。
- 再发一个 11 MB 的请求体，期望得到第 2 条的 `413 PAYLOAD_TOO_LARGE` 封套。

产品侧回归：Atlas 改完后，我们在生产上重跑 2026-09-29 失败的那份招标文件的解读，
并用系统验证页（`/console/diagnostics`）的 Atlas 活体探测确认四条路由仍为 4/4。结果会回复在本函的后续函里。

## 联系

- 失败的那次解读：工作流 `bid-interpretation-eb6b8790-3996-4866-acd1-37561574333c`，
  Atlas 日志时间 2026-09-29 11:21:53Z 与 11:22:04Z。
- 本产品调用 Atlas 的唯一出口：`backend/project-name-python/czghagent_ai/services/atlas_provider.py`；
  operation 到路由的映射：`backend/project-name-python/czghagent_ai/services/atlas_endpoints.py`。
