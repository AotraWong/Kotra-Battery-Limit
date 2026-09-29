# Kotra Battery Limit

## 引言

适用于 Apple Silicon / Asahi Linux 的小型 PySide6 充电阈值窗口和 KDE 托盘工具。界面为中文，固定使用 `/sys/class/power_supply/macsmc-battery/`。

> 这是AotraWong Vibe Coding 出来的第一个程序！
> 
> 果然对于IT而言，开发从遇到问题开始（
> 
> Kotra Battery Limit 是为了致敬 KDE 的那些程序而命名的（虽然说有空格）

## Alpha版 更新说明

* 新增 英文UI、充/放电功率显示、关于页面、日志
* 更改 现在启动后会释放终端，左键点击托盘不会直接打开主页面（与右键行为一致）

## 运行

当前这台机器已安装 Python 3、PySide6 和 pkexec，可以直接运行：

```bash
cd ~/Documents/code/Kotra-Battery-Limit
python3 app.py
```

普通启动会自动转到后台，终端立即返回提示符，关闭终端后程序仍继续运行。日志默认写入 `~/.local/state/kotra-battery-limit/app.log`（设置 `XDG_STATE_HOME` 时遵循该目录）。从托盘菜单退出程序。前台和后台模式均会将带时间戳的启动、电池状态变化、阈值操作、授权结果及退出记录立即写入日志；相同状态不会每 5 秒重复记录。需要查看实时错误时使用 `--foreground`；`--smoke-test` 始终在前台运行并返回测试结果。

其他机器需安装发行版提供的 Python 3、PySide6、polkit，以及桌面的 polkit 认证代理。也可通过 `requirements.txt` 在虚拟环境中安装 GUI 依赖。授权助手只使用系统 `/usr/bin/python3` 的标准库。

```bash
python3 app.py --foreground  # 前台调试，日志输出到当前终端
python3 app.py --tray   # 启动到托盘；托盘不可用时显示窗口
python3 app.py --demo   # 无需硬件，模拟应用设置
```

- 电量优先使用 `energy_now / energy_full`，与本机 UPower 的能量比例一致；不可用时依次回退到 `charge_now / charge_full`、`capacity`。显示一位小数，与桌面可能存在刷新时间和取整差异。悬停电量可查看来源及内核原始值。充电阈值仍原样写入驱动，不按显示电量换算。
- 窗口和托盘显示充电/放电功率（W，保留一位小数）。这是电池端净功率，不是充电器总输出功率。优先读取 macsmc 的 `power_now`（微瓦），缺失时以 `voltage_now × current_now` 估算；没有有效读数时显示“不可用”。正值表示充电，负值表示放电。
- 每 5 秒刷新电量、充电状态、功率、实际阈值；刷新不覆盖正在编辑的数值。
- 预设：75–80%、55–60%、100 / 100（允许充满）。选择后点“应用”才修改。
- 普通用户运行界面；点击应用后，`pkexec` 通过桌面认证代理请求授权，并执行独立助手。无需使用 sudo 启动 GUI。
- 关闭窗口后留在托盘；托盘右键菜单可打开、选预设或退出。授权期间禁止退出，避免中断写入。
- 没有接口时显示错误并禁用应用。首次运行只读取当前设置。

## 应用菜单与登录启动（可选）

在项目目录执行：

```bash
python3 install_desktop.py              # 添加应用菜单入口
python3 install_desktop.py --autostart  # 同时添加用户登录自启动
python3 install_desktop.py --uninstall  # 移除两个入口，保留代码
```

入口引用当前源代码目录，请勿随后移动或删除目录。登录自启动只开启托盘，不自动恢复或写入阈值。脚本默认使用系统 Python，适合当前已安装 PySide6 的环境。

## 权限与行为

助手只接受两个整数，要求 `0 ≤ start < end ≤ 100`，并允许驱动的特殊状态 `100 / 100`，固定写入 macsmc-battery 的两个阈值文件。不接受自定义文件路径，不调用 shell，不安装免密码 polkit 规则。`python3 -I` 隔离用户模块搜索路径。系统授权窗口显示的是 Python 命令；本项目源码在用户目录中，属于需要信任的本地代码，应用前请确认代码来源。

跨区间切换时按合适顺序写入，避免中间出现起始阈值高于停止阈值。随后读回内核接受的实际值（驱动可能取整）。两个 sysfs 写入不是原子事务；失败时尝试恢复原设置，并报告恢复后的数值或恢复失败。请避免同时用其他电池管理工具修改这两个文件。

该程序不强制放电，不提供充电速度控制或校准。停止阈值不会把已有高电量自动降下来。100% 预设解除充电上限，驱动可读回 100 / 100，表示允许充满。重启后是否保留设置取决于固件/驱动；程序不安装系统服务，不自动重写阈值。退出后也不重置内核设置。

## 验证

```bash
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 app.py --demo --smoke-test
QT_QPA_PLATFORM=offscreen python3 app.py --smoke-test
```

单元测试使用模拟 sysfs，覆盖阈值验证、跨区间写入顺序、部分写入失败后的恢复、驱动取整与缺失接口。冒烟测试只构建窗口并读取，不实际提权或写硬件。

接口参考：[Linux power supply ABI](https://github.com/torvalds/linux/blob/master/Documentation/ABI/testing/sysfs-class-power)、[Qt QSystemTrayIcon](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html)。

## 关于与诊断

主窗口按钮和托盘菜单均可打开“关于与诊断”，显示版本 **Beta 1**、作者 **AotraWong**、[GitHub 页面](https://github.com/aotrawong/kotra-battery-limit) 及项目现有 GNU GPL v3 许可证。可直接查看本地 LICENSE 全文。

诊断页列出数据接口、实际电量及功率来源、当前读数和运行环境；打开页面或点击“刷新诊断”更新。演示模式明确使用模拟数据。“打开日志”通过系统默认应用打开运行日志，日志尚未生成或打开失败时会显示提示。

macsmc 的起始阈值可能由停止阈值派生，写入起始值可能被驱动忽略。应用以读回值为准；100 / 100 是合法的解除限制状态，不会触发回滚。

## 界面语言 / Interface language

点击主窗口底部的 **English / 中文** 即时切换主窗口、托盘和关于与诊断页；语言选择会被保存，切换不会改变阈值或丢失未应用的编辑。中文表述保留当前版本。

Click **English / 中文** at the bottom of the main window to switch the UI, tray and About & Diagnostics page. The selection is saved without changing battery thresholds or pending edits.

终端启动提示、命令帮助及助手错误采用英语在前、中文在后的双语输出。助手成功返回的 JSON 仍是供 GUI 读取的机器协议。第三方 Qt、系统和 Python 自身的诊断不由本程序翻译。

## Wayland 托盘菜单

在提供 StatusNotifierWatcher 的桌面上，使用原生 StatusNotifierItem 菜单（`ItemIsMenu=true`），由桌面同时处理左右键，不依赖主窗口可见性。需要系统的 `python3-dbus` 和 `python3-gobject`（当前机器已安装）；缺少依赖或托盘服务时回退 Qt 托盘，日志会说明回退原因。

原生托盘回归验证（独立总线，不操作真实电池）：

```bash
dbus-run-session -- python3 tests/native_tray_probe.py
```
