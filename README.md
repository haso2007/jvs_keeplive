# JVS Keep Alive

使用 Playwright 无头浏览器定时刷新 JVS WebUI 聊天页面，让前端 JS 正常执行，维持 WebSocket 连接和 Token 刷新，避免关闭网页后登录态失效。

## 原理

与简单的 HTTP 请求不同，本脚本启动一个真正的无头浏览器来加载页面，前端 JS 会正常运行，效果等同于你一直开着浏览器标签页。

## 文件说明

- `jvs_keep_alive.py`：主脚本（Playwright 版）
- `jvs_keep_alive.template.json`：配置模板
- `jvs_keep_alive.json`：你的本地实际配置文件，不会提交到 Git
- `jvs_keep_alive.log`：运行日志，不会提交到 Git

## 安装依赖

```bash
pip install playwright
playwright install chromium
```

`playwright install chromium` 会下载约 150MB 的 Chromium 浏览器。

## 获取 Cookie

1. 登录 JVS WebUI，并进入实际要保活的聊天页面，例如：
   - `https://jvs.wuying.aliyun.com/chat?currentWuyingServerId=...`
2. 打开浏览器开发者工具（F12）
3. 在 `Network` 中找到这个 **chat 会话页面对应的请求**：
   - 请求名通常类似 `chat?currentWuyingServerId=...`
4. 点击该请求，在 `Headers` 中复制完整 `Cookie` 值
5. 不要随便从其它无关页面复制 Cookie，优先使用 **chat 会话页面当前请求** 的 Cookie

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

- `cookies`：从浏览器 **chat 会话页面请求** 中复制的完整 Cookie
- `interval`：页面刷新间隔，单位秒，默认 `600`（10 分钟）

## 运行

默认无头模式（不显示浏览器窗口）：

```bash
python jvs_keep_alive.py
```

有头模式（显示浏览器窗口，方便调试）：

```bash
python jvs_keep_alive.py --headed
```

指定刷新间隔：

```bash
python jvs_keep_alive.py --interval 300
```

## 如何确认是否有效

运行后日志里应出现：

```text
[OK] Page loaded - Title: ...
[OK] Heartbeat #1 - Title: ...
```

日志文件位于脚本同目录下：

```text
jvs_keep_alive.log
```

也可以检查 `jvs_keep_alive.json` 中的 `last_updated` 是否持续变化。

## 更新 Cookie

如果 Cookie 失效：

1. 重新登录网页，进入 chat 会话页面
2. 再次复制新的 `Cookie`
3. 替换 `jvs_keep_alive.json` 中的 `cookies`
4. 保存文件

脚本会自动重载新配置，无需重启。

## 资源占用

- 无头模式内存约 150-250MB（相当于一个 Chrome 标签页）
- 页面空闲时 CPU 几乎为零

## 注意

- 不要把真实 `jvs_keep_alive.json` 提交到 GitHub
- 不要公开分享你的 Cookie
