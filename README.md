# pjsk查询插件

一个基于AstrBot的 Project SEKAI（世界计划：缤纷舞台）查询插件，支持卡牌查询、歌曲查询、榜线查询等功能。默认查询简中服资料。

## 功能特性

- 卡牌查询：支持卡牌名、卡牌 ID、角色 ID、角色名/角色英文名搜索，附带卡图，多结果自动合并转发
- 卡牌发布时间显示为现实时间，不再是时间戳
- 角色查询：按角色姓名、英文名或角色 ID 查询
- 歌曲查询：按歌名、ID、作词、作曲、编曲查询
- 谱面查询：按歌曲 ID 或歌名查询各难度等级与物量
- 活动查询：按活动名或活动 ID 查询
- 当前活动：查询主数据中正在进行的活动
- 活动榜线：查询当前活动或指定活动的档位分数线，支持多种统计间隔
- 玩家查询：通过 Haruki-Sekai-API 查询指定玩家资料
- 玩家绑定：按 QQ 保存多个玩家绑定，可查看/解除绑定
- 随机选曲：随机抽取一首歌曲，可按关键词筛选
- 群白名单：可限制只有指定 QQ 群可以使用本插件

## 指令

| 指令 | 用途 | 示例 |
| --- | --- | --- |
| `查卡 <关键词>` | 按卡牌名、ID、角色名/角色 ID 查询卡牌，返回文字与卡图 | `查卡 初音` |
| `查角色 <关键词>` | 按角色姓名、英文名或 ID 查询角色 | `查角色 初音未来` |
| `查曲 <关键词>` | 按歌名、ID、作词、作曲、编曲查询歌曲 | `查曲 千本樱` |
| `查谱面 <歌曲 ID 或关键词>` | 查询歌曲各难度谱面等级与物量 | `查谱面 1` |
| `查活动 <关键词>` | 按活动名或活动 ID 查询活动 | `查活动 177` |
| `当前活动` | 查询当前正在进行的活动 | `当前活动` |
| `查榜线 [档位] [间隔]` | 查询当前活动榜线 | `查榜线 1000 1h` |
| `查活动榜线 <活动> [档位] [间隔]` | 查询指定活动榜线 | `查活动榜线 177 1000 1h` |
| `查玩家 <玩家ID> [服务器]` | 查询玩家资料 | `查玩家 123456 cn` |
| `绑定玩家 <玩家ID> [服务器]` | 绑定本 QQ 的玩家账号 | `绑定玩家 123456 cn` |
| `解除绑定 [服务器或序号]` | 解除已绑定的玩家 | `解除绑定 cn` |
| `玩家状态 [序号或服务器]` | 查看已绑定玩家的状态 | `玩家状态 1` |
| `随机曲 [关键词]` | 随机抽取一首歌曲，可按关键词筛选 | `随机曲 初音` |
| `pjsk帮助` | 生成美观的帮助图片 | `pjsk帮助` |

### 榜线命令说明

- 档位支持数字或 `T` 前缀，例如 `1000`、`T1000`。
- 不填档位时默认查询：`200、500、1000、5000、10000`。
- 间隔支持：

| 输入 | 间隔 |
| --- | --- |
| `15m` / `15min` / `15分钟` / `900` | 15 分钟 |
| `1h` / `1hour` / `1小时` / `3600` | 1 小时 |
| `6h` / `6hour` / `6小时` / `21600` | 6 小时 |
| `24h` / `24hour` / `1d` / `1天` / `86400` | 24 小时 |

示例：

```text
查榜线
查榜线 1000
查榜线 1000 15m
查活动榜线 177
查活动榜线 177 5000 6h
```

### 玩家命令说明

```text
查玩家 123456 cn
绑定玩家 123456 cn
玩家状态
玩家状态 1
玩家状态 cn
解除绑定 cn
解除绑定 1
```

- 服务器可选：`cn`、`jp`、`en`、`tw`、`kr`，不填默认使用 `region` 配置。
- 绑定按 QQ 保存，可绑定多个玩家。
- `玩家状态` 不带参数时显示全部绑定，也可以按序号或服务器筛选。
- 玩家查询依赖 Haruki-Sekai-API，默认地址为 `http://127.0.0.1:9999`。

### Haruki-Sekai-API 玩家功能配置

玩家查询指令默认**关闭**，需要额外部署 `Haruki-Sekai-API` 后才能使用。

#### 1. 获取 API 程序

从 Haruki-Sekai-API 仓库获取构建产物或自行编译：

```text
https://github.com/Team-Haruki/Haruki-Sekai-API
```

也可以使用你本地的 `haruki-sekai-api.exe`。

#### 2. 创建配置文件

参考仓库根目录的示例文件，复制为：

```text
haruki-sekai-configs.yaml
```

必须根据你要查询的服务器填写对应配置，例如：

- `backend.port`：默认 `9999`
- `servers.cn.api_url`：当前国服 API 地址
- `servers.cn.require_cookies` / `account_dir`：需要能访问游戏服务器的账号/凭据
- `servers.cn.aes_key_hex` / `aes_iv_hex`：国服加密参数
- 其他服务器同理

具体字段含义以仓库文档和 `haruki-sekai-configs.example.yaml` 注释为准。

#### 3. 启动 API

在 `haruki-sekai-configs.yaml` 同目录下运行：

```bash
haruki-sekai-api.exe
```

默认监听：

```text
http://127.0.0.1:9999
```

#### 4. 验证接口

用浏览器或 curl 测试：

```text
http://127.0.0.1:9999/api/cn/123456/profile
```

能返回 JSON 即部署成功。

#### 5. 开启插件玩家功能

在插件配置中设置：

```json
{
  "sekai_api_url": "http://127.0.0.1:9999",
  "enable_player_commands": true
}
```

然后重载插件或重启 AstrBot。

> 如果你不需要玩家查询，保持 `enable_player_commands: false` 即可，其它功能不受影响。

### 常用别名

- `查卡`：`pjsk查卡`、`查卡牌`
- `查榜线`：`当前榜线`、`pjsk榜线`、`sk线`
- `查活动榜线`：`活动榜线`、`pjsk活动榜线`
- `查玩家`：`pjsk查玩家`
- `绑定玩家`：`pjsk绑定玩家`
- `解除绑定`：`解绑`、`pjsk解除绑定`
- `玩家状态`：`我的玩家`、`pjsk玩家状态`
- `pjsk帮助`：`pjskhelp`、`世界计划帮助`

## 配置

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `data_source` | Haruki 主数据地址 | `https://sekai-master-cdn.haruki.seiunx.com` |
| `region` | 查询区服：`cn`、`jp`、`en`、`tw`、`kr` | `cn` |
| `event_tracker_url` | Haruki 公开榜线服务地址 | `https://toolbox-api-direct.haruki.seiunx.com/event-tracker` |
| `request_timeout` | 请求公开数据源的超时时间（秒） | `15` |
| `cache_ttl` | 主数据内存缓存时间（秒） | `1800` |
| `result_limit` | 模糊查询最多返回结果数 | `5` |
| `sekai_api_url` | Haruki-Sekai-API 地址 | `http://127.0.0.1:9999` |
| `enable_player_commands` | 是否启用查玩家/绑定玩家/玩家状态等指令 | `false` |
| `group_whitelist` | 群白名单，填写允许使用的 QQ 群号；留空表示所有群可用 | `[]` |

### 群白名单示例

```json
{
  "group_whitelist": ["123456789"]
}
```

留空或不配置表示所有群都可以使用。

### data_source 说明

默认使用 Haruki CDN：

```text
https://sekai-master-cdn.haruki.seiunx.com
```

也可以使用完整的 raw.githubusercontent.com 仓库地址，插件会自动识别并避免重复拼接仓库名：

```text
https://raw.githubusercontent.com/Team-Haruki/haruki-sekai-sc-master/main
```

## 数据来源与说明

- 游戏主数据来自 Haruki Dev Team 公开镜像/CDN。
- 榜线数据来自 Haruki Toolbox 的公开 event-tracker 接口。
- 玩家资料查询依赖 Haruki-Sekai-API。
- 数据准确性、更新频率和可用性由镜像与接口提供方决定。
