# Timeless Harness

[English](README.md) | [繁體中文](README.zh-TW.md)

> 用證據治理可重用 Agent 工作流。

![Timeless Harness](assets/timeless-harness-thumbnail.png)

現代 Agent 已經很會規劃、寫程式、研究、測試與審查。增加一套工作流可能讓它更好，也可能拖慢它、製造儀式，甚至帶來新錯誤。

Timeless Harness 只問一個問題：

**這套可重用 Agent 工作流還值得它帶來的成本嗎？**

它治理 Skill、指令、記憶規則、評估器與修復方法。它不包住一般任務。平常先讓原生 Agent 工作，只有當可重用方法本身需要檢查時才使用 Timeless。

## 一分鐘理解產品

Timeless 只有兩個核心部分：

- [`SKILL.md`](SKILL.md) 給 Agent 一套精簡的生命週期政策：`keep | narrow | revise | retire | unresolved`。
- [`tools/harness_governor.py`](tools/harness_governor.py) 建立配對的原生組與工作流組、封存證據、準備盲評、測量成本，最後產生暫定的生命週期候選決策。

```text
可重用工作流提出改善主張
              |
凍結任務、評分規則、工作區、模型與成本規則
              |
分開執行原生基準組與工作流實驗組
              |
盲評答案、產物清單與外部評估結果
              |
合併品質、Token 與時間成本
              |
keep | narrow | revise | retire | unresolved
```

單一配對只能用來篩選，不能證明普遍效果。最終生命週期決策需要多個代表性案例、重複結果，以及在看見結果前就設定好的停止條件。

## 用自我修正證明方法

第一版 Timeless 曾經試圖包住一般 Agent 工作。它自己的評估顯示，這反而比讓強大模型自行工作更差。

完整且已去識別的證據公開在 [`examples/self-audit`](examples/self-audit)，包括 4 個任務、24 份匿名輸出、72 筆評分、36 次盲評偏好、評審筆記、解盲對照與檔案雜湊。

不需要 API key、網路或模型額度即可重算：

```bash
RESULT="$(mktemp -d)/timeless-self-audit"
python3 tools/harness_governor.py self-audit \
  --evidence examples/self-audit \
  --output "$RESULT"
```

預期輸出：

```text
EVIDENCE: VERIFIED 44 FILES
PREFERENCES: NATIVE 19 | TIMELESS 6 | TIES 11
MEAN SCORE: NATIVE 3.991 | TIMELESS 3.889
FATAL OMISSIONS: NATIVE 0 | TIMELESS 0
UNNECESSARY PROCESS: NATIVE 0 | TIMELESS 9
DECISION: RETIRE TESTED GENERAL WRAPPER
CURRENT GOVERNOR: UNRESOLVED
```

失敗不是抽象概念。舊版會在沒有必要時加入固定三次發布檢查，卻沒有改善答案。因此 Timeless 刪除了自動包住一般任務、固定流程階段、持久工作區儀式與普遍優越性宣稱。

這份證據可以重現淘汰舊版通用 Wrapper 的決策。它不能證明新版窄範圍 Governor 更好。這項主張目前仍是 `unresolved`。詳見 [`EVALUATION.md`](EVALUATION.md)。

Timeless 沒有丟掉求真、根因修復、完整成品檢查與學習。它改變了這些方法的角色。只有在證據爭議、重複失敗或需要形成長期經驗時，才載入對應深度；不再把它們變成每個任務外面的強制儀式。Governor 讓這些可重用規則持續接受實際價值與成本的檢驗。

## 它不是另一套工作流套件

| 產品 | 主要工作 |
| --- | --- |
| Codex 或 Claude Code | 完成任務 |
| Superpowers 等工作流套件 | 增加可重用的任務執行方法 |
| Eval Framework | 測量輸出 |
| Timeless Harness | 治理一套可重用工作流應該保留、縮小、修改或刪除 |

Timeless 可以使用評估器，但它不是 Eval Framework。它治理的是包圍在日益強大 Agent 外層的指令負債。

## 評審測試方式

需要 Git 與 Python 3.10 以上版本。自我審計與測試只使用 Python 標準函式庫。

```bash
git clone --branch v0.1.0 --depth 1 \
  https://github.com/FuturizeRush/timeless-harness.git
cd timeless-harness

RESULT="$(mktemp -d)/timeless-self-audit"
python3 tools/harness_governor.py self-audit \
  --evidence examples/self-audit \
  --output "$RESULT"

python3 -m unittest discover -s tests -v
```

這條路徑不會呼叫模型，也不需要憑證。

## 安裝 Skill

兩個命令都會安裝固定的 `v0.1.0` 版本，且拒絕覆寫現有目錄。

### Codex

```bash
(
  set -eu
  VERSION=v0.1.0
  DEST="${CODEX_HOME:-$HOME/.codex}/skills/timeless-harness"
  [ ! -e "$DEST" ] || { printf 'Refusing to overwrite: %s\n' "$DEST" >&2; exit 1; }
  mkdir -p "$(dirname "$DEST")"
  trap 'rm -rf "$DEST"' EXIT HUP INT TERM
  git clone --filter=blob:none --no-checkout \
    https://github.com/FuturizeRush/timeless-harness.git "$DEST"
  git -C "$DEST" checkout --quiet --detach "$VERSION^{commit}"
  trap - EXIT HUP INT TERM
)
```

重新開啟 Codex Session，然後說：

```text
Use $timeless-harness to review whether this reusable workflow should be kept, narrowed, revised, or retired.
```

### Claude Code

```bash
(
  set -eu
  VERSION=v0.1.0
  DEST="$HOME/.claude/skills/timeless-harness"
  [ ! -e "$DEST" ] || { printf 'Refusing to overwrite: %s\n' "$DEST" >&2; exit 1; }
  mkdir -p "$(dirname "$DEST")"
  trap 'rm -rf "$DEST"' EXIT HUP INT TERM
  git clone --filter=blob:none --no-checkout \
    https://github.com/FuturizeRush/timeless-harness.git "$DEST"
  git -C "$DEST" checkout --quiet --detach "$VERSION^{commit}"
  trap - EXIT HUP INT TERM
)
```

重新開啟 Claude Code Session，然後呼叫：

```text
/timeless-harness Review whether this reusable workflow should be kept, narrowed, revised, or retired.
```

在重要工作中使用第三方 Skill 前，請先自行審查內容。

## 用 Codex 進行前瞻配對篩選

Live 模式是選用功能，會消耗兩次 Codex 執行。只能使用可信任的本機輸入。

準備任務、待審查 Skill、評分規則與共同起始工作區：

```bash
python3 tools/harness_governor.py prepare \
  --task /path/to/TASK.md \
  --skill /path/to/SKILL.md \
  --rubric /path/to/RUBRIC.md \
  --source /path/to/start-workspace \
  --output /tmp/timeless-experiment \
  --max-cost-ratio 1.25
```

也可以加入可信任的外部評估器：

```text
--evaluator /path/to/read-only-evaluator
```

評估器會以候選工作區作為目前目錄。若它修改工作區，執行會失敗。

執行配對：

```bash
python3 tools/harness_governor.py run \
  --experiment /tmp/timeless-experiment \
  --model gpt-5.6-sol \
  --reasoning ultra \
  --sandbox workspace-write \
  --run-id screen-1 \
  --allow-live
```

建立盲評資料：

```bash
python3 tools/harness_governor.py blind \
  --experiment /tmp/timeless-experiment \
  --run-id screen-1
```

只把 `runs/screen-1/grader/` 交給評審，隱藏 `private/`。評審完成 verdict JSON 後：

```bash
python3 tools/harness_governor.py decide \
  --experiment /tmp/timeless-experiment \
  --run-id screen-1 \
  --verdict /path/to/verdict.json
```

終端只會顯示 `PROVISIONAL SCREEN` 與 `CANDIDATE`，不會把單一配對冒充最終生命週期結論。

## 安全與證據邊界

- Live 呼叫必須明確加入 `--allow-live`，工具不會暗中消耗額度。
- 拒絕 `danger-full-access`。
- 複製工作區前會拒絕 `.env`、認證檔與私鑰等常見敏感檔案。
- 兩組條件在不同的隨機暫存目錄中執行，第一組刪除後才建立第二組。這能降低意外互讀，但不是作業系統等級的隔離保證。
- 最終工作區、Capture、Telemetry 與檔案權限都會進入雜湊封存。工具可以偵測後續不一致，但雜湊不是數位簽章，也不能證明證據由誰產生。
- 外部評估器只會收到獨立複本，不會取得 Codex 認證或候選 Capture 路徑。若它修改獨立複本，執行就會失敗。
- 盲評包包含答案、匿名產物摘要與選用的外部評估結果，但不會自動證明評估器本身正確。
- 本機 Live 模式只適合可信任程式碼。不可信任程式碼必須放在外部 Sandbox。

## 支援與測試環境

- 已測 Skill Host：Codex CLI `0.144.1` on macOS，2026-07-16
- 已測相容目標：Claude Code `2.1.157` on macOS，2026-07-16
- Governor：Python `3.10+`，只使用標準函式庫
- 本機測試：Python `3.14.5`、Git `2.50.1`、macOS
- Live Governor Runner：僅支援 Codex

Markdown Skill 可能能在 Windows 與 Linux 使用，但目前尚未驗證。

## 如何使用 Codex 與 GPT-5.6

Codex 是主要工程環境，用來把提交要求反推成驗收條件、實作 Governor、執行測試、審計 Repo、審查主張、檢視原始評估資料，以及刪除無法證明價值的功能。

GPT-5.6 Sol 搭配 ultra reasoning，透過 Codex 參與實作、對抗式審查、安全審查、證據分析、文件整理，以及淘汰舊版 Wrapper 的產品決策。不同上下文中的審查找出了具體漏洞，包括 `NaN` 成本規則繞過與可被事後修改的執行證據。這些問題已修復並加入測試。

人類作者決定產品目標、隱私邊界、評估政策與最後發布決策。Repo 不包含私人程式碼、憑證、對話文字或可識別的專案資料。

## Repo 結構

```text
SKILL.md                    精簡的 Runtime 生命週期政策
tools/harness_governor.py  只用標準函式庫的 Governor CLI
tests/                      證據完整性與生命週期契約測試
examples/self-audit/       完整公開的自我修正證據
EVALUATION.md               結果、限制與下一步驗證
references/                 選用的深入方法
docs/PHILOSOPHY.md          人文與工程憲章
agents/openai.yaml          Codex 介面 Metadata
```

完整哲學保留在 [`docs/PHILOSOPHY.md`](docs/PHILOSOPHY.md)，不會載入一般任務。每一條 Runtime 指令都必須值得它占用的 Context 成本。

## License

[MIT](LICENSE)
