@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

echo ============================================
echo  河海课表 - 本地更新（GitHub Actions 不可用时的备用方案）
echo ============================================
echo.

if not exist "scripts\local_secrets.json" (
  echo 缺少 scripts\local_secrets.json
  echo 请先复制 scripts\local_secrets.example.json 为 local_secrets.json，填入学号、密码与同步口令。
  pause
  exit /b 1
)

echo [1/3] 抓取课表并加密...
python scripts\fetch_schedule.py --out web\data\schedule.enc.json --secrets-file scripts\local_secrets.json
if errorlevel 1 (
  echo 抓取失败：请检查凭据、网络或教务系统是否正常。
  pause
  exit /b 1
)

echo.
echo [2/3] 提交改动...
git add web\data\schedule.enc.json
git diff --staged --quiet
if errorlevel 1 (
  git commit -m "chore: 本地更新课表数据"
) else (
  echo 课表数据没有变化，跳过提交。
)

echo.
echo [3/3] 推送到 GitHub...
git push
if errorlevel 1 (
  echo 推送失败：请确认仓库远端与登录凭据可用。
  pause
  exit /b 1
)

echo.
echo 完成！手机上打开网页（或等待 Pages 部署完成后刷新）即可看到最新课表。
pause
