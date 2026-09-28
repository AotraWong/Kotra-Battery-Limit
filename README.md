# Kotra Battery Limit

## 引言

适用于 Apple Silicon / Asahi Linux 的小型 PySide6 充电阈值窗口和 KDE 托盘工具。界面为中文，固定使用 `/sys/class/power_supply/macsmc-battery/`。

> 这是AotraWong Vibe Coding 出来的第一个程序！
> 
> 果然对于IT而言，开发从遇到问题开始（
> 
> Kotra Battery Limit 是为了致敬 KDE 的那些程序而命名的（虽然说有空格）

## 运行

当前这台机器已安装 Python 3、PySide6 和 pkexec，可以直接运行：

```bash
cd /home/aotra/code/asahi-battery-limit
python3 app.py
```

其他机器需安装发行版提供的 Python 3、PySide6、polkit，以及桌面的 polkit 认证代理。也可通过 `requirements.txt` 在虚拟环境中安装 GUI 依赖。授权助手只使用系统 `/usr/bin/python3` 的标准库。

```bash
python3 app.py --tray   # 启动到托盘；托盘不可用时显示窗口
python3 app.py --demo   # 无需硬件，模拟应用设置
```

- 电量优先使用 `energy_now / energy_full`，与本机 UPower 的能量比例一致；不可用时依次回退到 `charge_now / charge_full`、`capacity`。显示一位小数，与桌面可能存在刷新时间和取整差异。悬停电量可查看来源及内核原始值。充电阈值仍原样写入驱动，不按显示电量换算。
- 每 5 秒刷新电量、充电状态、实际阈值；刷新不覆盖正在编辑的数值。
- 预设：75–80%、55–60%、95–100%。选择后点“应用”才修改。
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

助手只接受两个整数，强制 `0 ≤ start < end ≤ 100`，固定写入 macsmc-battery 的两个阈值文件。不接受自定义文件路径，不调用 shell，不安装免密码 polkit 规则。`python3 -I` 隔离用户模块搜索路径。系统授权窗口显示的是 Python 命令；本项目源码在用户目录中，属于需要信任的本地代码，应用前请确认代码来源。

跨区间切换时按合适顺序写入，避免中间出现起始阈值高于停止阈值。随后读回内核接受的实际值（驱动可能取整）。两个 sysfs 写入不是原子事务；失败时尝试恢复原设置，并报告恢复后的数值或恢复失败。请避免同时用其他电池管理工具修改这两个文件。

该程序不强制放电，不提供充电速度控制或校准。停止阈值不会把已有高电量自动降下来。100% 预设是 95–100% 阈值，并非驱动的“清除限制”命令。重启后是否保留设置取决于固件/驱动；程序不安装系统服务，不自动重写阈值。退出后也不重置内核设置。

## 验证

```bash
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 app.py --demo --smoke-test
QT_QPA_PLATFORM=offscreen python3 app.py --smoke-test
```

单元测试使用模拟 sysfs，覆盖阈值验证、跨区间写入顺序、部分写入失败后的恢复、驱动取整与缺失接口。冒烟测试只构建窗口并读取，不实际提权或写硬件。

接口参考：[Linux power supply ABI](https://github.com/torvalds/linux/blob/master/Documentation/ABI/testing/sysfs-class-power)、[Qt QSystemTrayIcon](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html)。
