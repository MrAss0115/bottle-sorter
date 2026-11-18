# 退出SSH后持续运行

适用已确认环境：Ubuntu22.04、ubuntu用户、/home/ubuntu/bottlesorter项目、.venv312环境及已安装的cloudflared。

## 安装

1. 用MobaXterm左侧SFTP把两个.sh上传到 /home/ubuntu/bottlesorter/。
2. 若旧的前台后端和Tunnel还在运行，在各自原窗口按Ctrl+C停止；已经随SSH退出的无需处理。安装脚本不会杀进程，8000占用时会停止并提示。
3. 以ubuntu用户执行，不要sudo bash：

```bash
cd /home/ubuntu/bottlesorter &&
bash install-bottlesorter-services.sh
```

脚本检查依赖和路径，创建两个systemd服务，保留原数据库和密钥，不打印口令。遇到未知的同名服务或override时拒绝覆盖。

- bottlesorter：原后端，监听127.0.0.1:8000。
- bottlesorter-tunnel：Quick Tunnel，转发到上述后端。

两者均设置开机启动和异常退出后重启。脚本最后Backend health: OK表示后端本机检查通过；Tunnel建立连接是异步的，还需验证外部访问。

## 检查

```bash
sudo systemctl status bottlesorter bottlesorter-tunnel --no-pager
bash /home/ubuntu/bottlesorter/show-bottlesorter-url.sh
```

成功标准：两个服务active(running)，取到本次进程生成的HTTPS网址，从Windows访问该网址/api/health返回200及status=ok。没取到网址时稍后重试，并检查日志。

然后退出SSH，等约一分钟，从Windows再次访问/api/health。仍返回200才说明本次SSH断开后的访问验证成功。容量页面因缺心跳显示“设备离线”不代表后端停止。

## 维护

只改后端代码后，通常只需重启后端，避免主动重建临时Tunnel：

```bash
sudo systemctl restart bottlesorter
```

查看日志和开机启动状态：

```bash
sudo journalctl -u bottlesorter -n 60 --no-pager
sudo journalctl -u bottlesorter-tunnel -n 60 --no-pager
systemctl is-enabled bottlesorter bottlesorter-tunnel
```

停止并取消开机启动（不删除数据库）：

```bash
sudo systemctl disable --now bottlesorter-tunnel bottlesorter
```

## 限制

没有域名也可以后台维持Quick Tunnel，但它仍是临时测试入口，不保证长期可用。Tunnel进程重启或服务器重启后网址可能变化，要更新Postman base_url和浏览器地址；数据和RFID口令不会因此改变。

需要固定网址时，后续再使用接入Cloudflare的域名和Named Tunnel。这次没有配置固定网址，也没有修改设备端HTTPS能力。

两个脚本保存在E盘并做本地静态检查，尚未在你的Ubuntu安装。真实结果以远端命令输出及外部健康检查为准。

官方参考：https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
