# 业务数据说明

## 目录用途

- `raw/official_work_orders/`：按类别保存官方 Excel 与配套录音的本地副本。
- `processed/`：由脚本读取 Excel 后生成的标准化 json。
- `categories/`：事项分类目录。
- `departments/`：承办单位职责、排除职责和属地规则。
- `mock/`：用于开发和测试的脱敏模拟诉求及期望结果。

## 官方样例

数据来源为比赛官方提供的“信件类别示例工单及录音”。原始数据层同时保留 Excel 与配套录音；当前准备流程只匹配和读取 `*.xlsx`，不会打开、转写或分析录音。Excel 第一行是标题，第二行才是字段名。

标准字段包括：`source_id`、`accepted_at`、`source_channel`、`title`、`request_content`、`handling_departments`、`reply_content`、`region`、`category`、`urgent`、`repeat_request` 和 `source_file`。

## 初始数据准备（官方数据集获取）

本仓库的官方原始数据需从比赛官方渠道获取并放置到 `raw/official_work_orders/`，操作步骤与根目录 `README.md` 的「初始数据准备」章节一致：

1. 下载官方数据集：[12345赛题数据集-信件类别示例工单及录音.zip](https://pan.baidu.com/s/1ysOOYqmoAQTr_yJWQLXoyw?pwd=u9ca)，提取码：**u9ca**。

2. 打开官方数据集并解压，查看其中的 `信件类别示例工单及录音` 文件夹。

3. 将 `信件类别示例工单及录音` 文件夹中的所有文件全部复制到项目的 `backend\data\raw\official_work_orders` 目录中。

4. 在 `backend/` 目录下激活虚拟环境后执行预处理脚本：

```powershell
cd backend
# Windows 激活环境
.\venv\Scripts\Activate.ps1

# macOS 激活环境
source venv/bin/activate

python scripts/prepare_dataset.py data/raw/official_work_orders
```

> 更完整的安装与运行说明见仓库根目录 `README.md` 的「二、安装与运行」与「初始数据准备」章节。

## 安全边界

真实姓名、手机号、身份证号、详细地址和未经授权的录音不得进入公开仓库。历史办理单位、历史答复和 Mock 期望结果只用于开发演示，不代表当前正式权责或政策结论。共享任何处理结果前必须完成脱敏并确认比赛规则和授权范围。
