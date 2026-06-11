# Slasher Survivors — 割草遊戲 Demo + AWS 多 Region 後端

極簡割草型(horde-survival)PyGame 遊戲 Demo,搭配多 Region AWS 後端,提供
**遊戲日誌收集、成就系統、全球排行榜**,並具備**就近寫入 + 全球榜 + 跨區容災**能力。

## Monorepo 結構

```
.
├── game/        # PyGame 客戶端(極簡割草遊戲)
├── backend/     # FastAPI 後端(送分 / 排行榜 / 成就),容器化
└── infra/       # AWS CDK 基礎設施(多 Region,Task 5–7)
```

## 技術選型

| 層級 | 技術 |
|------|------|
| 遊戲 | PyGame |
| 後端 API | FastAPI + Uvicorn |
| 資料庫 | DynamoDB Global Tables(本地開發用 DynamoDB Local) |
| 運算 | ECS/Fargate + ALB |
| 路由/容災 | Route 53 latency-based routing + health check failover |
| 多 Region | `us-west-1`(主)+ `ap-east-2`(台北,次) |
| Log | CloudWatch Logs(遊戲結束事件) |
| IaC | AWS CDK |

## 快速開始(本地開發,免 AWS 認證)

### 遊戲

```bash
cd game
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.main          # 啟動遊戲
pytest                      # 跑測試
```

### 後端

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d        # 啟動 DynamoDB Local + API
pytest                      # 跑測試
```

## API

| Method | Path | 說明 |
|--------|------|------|
| POST | `/scores` | 送出一局成績,計算成就並記錄 game-over log |
| GET | `/leaderboard?limit=10` | 全球前 N 名 |
| GET | `/achievements/{nickname}` | 玩家已解鎖成就 |
| GET | `/health` | 健康檢查(ALB 用) |

## Git Flow 分支規範

| 分支 | 用途 |
|------|------|
| `main` | 穩定可發布版本,里程碑打 tag |
| `develop` | 整合分支,所有功能合流於此 |
| `feature/*` | 單一功能/任務,完成後以 `--no-ff` 合回 `develop` |
| `release/*` | 發布準備,由 `develop` 切出,驗證後合入 `main` 並打 tag |
| `hotfix/*` | `main` 緊急修正 |

> 注意:不直接 push 到 `main`。

## 進度

- [x] Task 1 — 專案骨架與本地開發環境
- [x] Task 2 — 極簡割草遊戲核心
- [x] Task 3 — 後端 API + DynamoDB Local
- [x] Task 4 — 遊戲串接後端
- [x] Task 5 — 單一 Region 基礎設施(CDK,`us-west-1`)
- [ ] Task 6 — 多 Region + Global Table + 容災
- [ ] Task 7 — 收尾與文件

## License

Released under the [MIT License](LICENSE).
