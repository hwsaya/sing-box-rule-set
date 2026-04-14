LATEST_SINGBOX=$(curl -s https://api.github.com/repos/SagerNet/sing-box/releases/latest | grep "browser_download_url.*linux-amd64.tar.gz" | cut -d '"' -f 4)
curl -sL "$LATEST_SINGBOX" | tar -xz
sudo mv sing-box-*/sing-box /usr/local/bin/