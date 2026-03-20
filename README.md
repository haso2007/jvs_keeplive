# JVS Keep Alive

通过定时请求 JVS WebUI 页面来维持会话，尽量避免关闭网页后登录态失效。

## 文件说明

- `jvs_keep_alive.py`：主脚本
- `jvs_keep_alive.template.json`：配置模板
- `jvs_keep_alive.json`：你的本地实际配置文件，不会提交到 Git
- `jvs_keep_alive.log`：运行日志，不会提交到 Git

## 使用前准备

1. 登录 JVS WebUI
2. 打开浏览器开发者工具（F12）
3. 在 `Network` 中点击任意请求
4. 在 `Headers` 里复制完整 `Cookie` 值

## 配置

复制模板文件：

```bash
cp jvs_keep_alive.template.json jvs_keep_alive.json
```

Windows CMD：

```bat
copy jvs_keep_alive.template.json jvs_keep_alive.json
```

然后编辑 `jvs_keep_alive.json`：

```json
{
  "cookies": "你的完整cookie字符串",
  "interval": 600,
  "last_updated": ""
}
```

- `cookies`：从浏览器复制的完整 Cookie
- `interval`：请求间隔，单位秒，默认 `600`（10 分钟）

## 运行

```bash
python jvs_keep_alive.py
```

## 可选参数

交互式写入配置：

```bash
python jvs_keep_alive.py --setup
```

临时指定 Cookie：

```bash
python jvs_keep_alive.py --cookie "k1=v1; k2=v2"
```

指定心跳间隔：

```bash
python jvs_keep_alive.py --interval 300
```

## 如何确认是否有效

运行后日志里应出现：

```text
[OK] Heartbeat #1 - Status: 200
```

日志文件：

```text
jvs_keep_alive.log
```

也可以检查 `jvs_keep_alive.json` 中的 `last_updated` 是否持续变化。

## 更新 Cookie

如果 Cookie 失效：

1. 重新登录网页
2. 再次复制新的 `Cookie`
3. 替换 `jvs_keep_alive.json` 中的 `cookies`
4. 保存文件

脚本会自动重载新配置，无需重启。

## 注意

- 不要把真实 `jvs_keep_alive.json` 提交到 GitHub
- 不要公开分享你的 Cookie
- 该脚本当前是通过保活网页登录态来维持会话，不保证一定能刷新业务侧 JWT
