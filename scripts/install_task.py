#!/usr/bin/env python3
"""注册 Windows 计划任务：每天定时同步课表。

抓取必须在你自己的电脑上跑（学校 WAF 会拦数据中心 IP），
所以用计划任务代替云端定时。电脑关机错过时间时，开机后会自动补跑。
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK_NAME = "HHU课表自动同步"
RUN_TIME = "19:00"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

TEMPLATE = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>河海课表：自动抓取课表并推送到 GitHub Pages</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>/c "{bat}" --auto</Arguments>
      <WorkingDirectory>{workdir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def main() -> int:
    bat = ROOT / "scripts" / "local_update.bat"
    if not bat.is_file():
        print(f"找不到 {bat}")
        return 1
    if not (ROOT / "scripts" / "local_secrets.json").is_file():
        print("请先创建 scripts/local_secrets.json（见 README），再安装计划任务。")
        return 1

    import datetime as dt

    start = dt.datetime.now().strftime("%Y-%m-%dT") + RUN_TIME + ":00"
    xml = TEMPLATE.format(start=start, bat=bat, workdir=ROOT)

    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-16") as handle:
        handle.write(xml)
        xml_path = handle.name

    result = subprocess.run(
        ["schtasks", "/create", "/tn", TASK_NAME, "/xml", xml_path, "/f"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    Path(xml_path).unlink(missing_ok=True)

    if result.returncode == 0:
        print(f"计划任务已创建：{TASK_NAME}")
        print(f"每天 {RUN_TIME} 自动同步；如果那时电脑关机，开机后会自动补跑。")
        print("查看或删除：任务计划程序 → 任务计划程序库 → " + TASK_NAME)
        return 0
    print("创建失败：")
    print((result.stdout or "") + (result.stderr or ""))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
