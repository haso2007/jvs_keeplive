# JVS Keep Alive

使用 Playwright 无头浏览器**常驻打开** JVS WebUI 聊天页面，让前端 JS 持续运行，维持 WebSocket 连接和 Token 自动刷新，避免关闭网页后 JWT 过期。

## 原理

脚本启动一个真正的无头浏览器加载 chat 页面后**保持打开不关闭**，前端 JS 持续运行，效果等同于你一直开着浏览器标签页。脚本只做状态监控，不会刷新页面，确保 WebSocket 连接和前端心跳不被中断。

## 文件说明

- `jvs_keep_alive.py`：主脚本（Playwright 版）
- `jvs_keep_alive.template.json`：配置模板
- `jvs_keep_alive.json`：你的本地实际配置文件，不会提交到 Git
- `jvs_keep_alive.log`：运行日志，不会提交到 Git
- `Dockerfile`：Docker 镜像构建文件
- `docker-compose.yml`：Docker Compose 编排文件

## 安装依赖

### 方式一：直接运行（Python 3.9+）

```bash
pip install playwright
playwright install chromium
```

脚本首次运行时也会自动安装缺失的依赖。

### 方式二：Docker（推荐用于 NAS / 服务器）

适用于系统 Python 版本较低（如 3.8）或不想污染系统环境的场景。

先完成下方「配置」步骤，再运行：

```bash
docker compose up -d
```

查看日志：

```bash
docker compose logs -f
```

停止：

```bash
docker compose down
```

重启（脚本更新后）：

```bash
docker compose down && docker compose up -d
```

容器设置了 `restart: unless-stopped`，NAS / 服务器重启后会自动恢复运行。

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
  "check_interval": 60,
  "last_updated": ""
}
```

- `cookies`：从浏览器 **chat 会话页面请求** 中复制的完整 Cookie
- `check_interval`：状态检查间隔，单位秒，默认 `60`（1 分钟）。仅用于监控页面是否存活，不会刷新页面

## 运行

默认无头模式（不显示浏览器窗口）：

```bash
python jvs_keep_alive.py
```

有头模式（显示浏览器窗口，方便调试）：

```bash
python jvs_keep_alive.py --headed
```

指定检查间隔：

```bash
python jvs_keep_alive.py --check-interval 120
```

## 后台长久运行

关闭终端窗口后脚本默认会被终止。以下方法可以让脚本在后台持续运行。

### PowerShell

后台运行，关闭窗口后仍继续：

```powershell
Start-Process -NoNewWindow -FilePath python -ArgumentList "jvs_keep_alive.py" -RedirectStandardOutput jvs_keep_alive_stdout.log -RedirectStandardError jvs_keep_alive_stderr.log
```

查看是否在运行：

```powershell
Get-Process python | Where-Object { $_.CommandLine -like '*jvs_keep_alive*' }
```

停止：

```powershell
Get-Process python | Where-Object { $_.CommandLine -like '*jvs_keep_alive*' } | Stop-Process
```

### Git Bash / WSL / Linux

后台运行，关闭终端后仍继续：

```bash
nohup python jvs_keep_alive.py > /dev/null 2>&1 &
echo $!  # 记下进程号
```

查看是否在运行：

```bash
ps aux | grep jvs_keep_alive
```

停止：

```bash
kill <进程号>
```

### Windows CMD

后台运行：

```bat
start /b python jvs_keep_alive.py > nul 2>&1
```

如果希望关闭 CMD 窗口后仍运行，可以用计划任务或包装成 Windows 服务。

### Windows 开机自启（计划任务）

```powershell
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\jvs_keep_alive.py" -WorkingDirectory "C:\path\to"
$trigger = New-ScheduledTaskTrigger -AtLogon
Register-ScheduledTask -TaskName "JVS_KeepAlive" -Action $action -Trigger $trigger -Description "JVS WebUI Keep Alive"
```

删除计划任务：

```powershell
Unregister-ScheduledTask -TaskName "JVS_KeepAlive" -Confirm:$false
```

## 如何确认是否有效

运行后日志里应出现：

```text
[OK] Page loaded - Title: JVS Claw
[OK] Page will stay open, frontend JS keeps running
[OK] Check #1 - Page alive - Title: JVS Claw
[OK] Check #2 - Page alive - Title: JVS Claw
```

如果出现 `Redirected to login` 则说明 Cookie 已失效，需要重新获取。

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

脚本检测到配置变化后会自动加载新 Cookie 并重新打开页面，无需重启。

## 资源占用

- 无头模式内存约 150-250MB（相当于一个 Chrome 标签页）
- 页面常驻后 CPU 几乎为零

## 注意

- 不要把真实 `jvs_keep_alive.json` 提交到 GitHub
- 不要公开分享你的 Cookie
