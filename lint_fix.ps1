# lint_fix.ps1 — One-click fixer for autoflake, isort, black, flake8

Write-Host "🔧 Removing unused imports and variables with autoflake..."
autoflake --remove-all-unused-imports --remove-unused-variables -ir .

Write-Host "🔧 Sorting imports with isort..."
isort .

Write-Host "🔧 Reformatting code with black..."
black .

Write-Host "🔍 Running flake8 for final lint check..."
flake8 .

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ All clean! Ready to commit." -ForegroundColor Green
} else {
    Write-Host "`n⚠️  flake8 still has issues. Check output above." -ForegroundColor Yellow
}
