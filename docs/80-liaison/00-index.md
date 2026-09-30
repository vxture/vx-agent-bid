# 80-liaison 索引

跨线联络函。**一函一事，按时间戳编号，只增不改**——已发出的函是那一刻双方共识的
记录，改它等于让归档失去作用。事实变了就再发一封，在新函里引用旧函。

命名：`{序号}-{YYMMDDHHMM}-{产品码}-{主题}.md`，与组织内其它仓一致。

| 文件 | 收件方 | 状态 | 内容 |
| --- | --- | --- | --- |
| [10-2609111009-tenderforge-atlas-endpoint-request.md](./10-2609111009-tenderforge-atlas-endpoint-request.md) | Atlas 线 | superseded（被 30 取代） | 请求登记并授权六个 endpoint：用途、上下文要求、生成参数、模型能力要求 |
| [20-2609111107-tenderforge-yucer-deploy-dir-trap.md](./20-2609111107-tenderforge-yucer-deploy-dir-trap.md) | yucer 线 | informational | DEPLOY_DIR 被 Windows 路径转换改写：症状、为什么无报错面、三条修正建议 |
| [30-2609142131-tenderforge-atlas-generic-routes.md](./30-2609142131-tenderforge-atlas-generic-routes.md) | Atlas 线 | informational | 改用四条通用路由、撤回六个专属 endpoint；operation 分档与各路由的模型下限 |
| [40-2609291955-tenderforge-atlas-request-body-limit.md](./40-2609291955-tenderforge-atlas-request-body-limit.md) | Atlas 线 | request | `/v1/chat` 请求体上限 100 KB 拒掉真实解读请求：证据、各环节请求体规模、请求提到 10 MB 并返回结构化 413 / 上下文超限码、公开路由容量；产品侧的分片承诺 |
