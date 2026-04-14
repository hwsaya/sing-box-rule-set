name: Build Rules
on:
  workflow_dispatch:
  schedule:
    - cron: "0 0 * * *"
  push:
    branches:
      - main

jobs:
  build:
    runs-on: ubuntu-latest
    # 核心修复：增加写入权限
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-go@v5
        with:
          go-version: '1.21'

      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Setup
        run: |
          pip install requests
          LATEST=$(curl -s https://api.github.com/repos/SagerNet/sing-box/releases/latest | grep "browser_download_url.*linux-amd64.tar.gz" | cut -d '"' -f 4)
          curl -sL "$LATEST" | tar -xz
          sudo mv sing-box-*/sing-box /usr/local/bin/
          go mod tidy
          go build -o geoip-tool .

      - name: Run
        run: python scripts/build.py

      - name: Push
        run: |
          cd output
          # 确保清理掉 geoip 产生的中间文本目录，只保留 .srs
          rm -rf text/
          git init
          git config --local user.name "github-actions[bot]"
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git checkout -b release
          git add .
          git commit -m "Update $(date +%Y%m%d)" || exit 0
          # 注意：这里我们使用 GitHub Actions 自动提供的环境变量，更安全
          git remote add origin "https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/${{ github.repository }}"
          git push -f origin release
