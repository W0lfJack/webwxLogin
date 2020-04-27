import requests
import time
import json
import os
import threading
import random
import re
from bs4 import BeautifulSoup


class Login(object):
    def __init__(self):
        self.session = requests.session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36"}
        self.UUID = ''
        self.tip = 0
        self.redirect_url = ''
        self.wxuin = ''
        self.wxsid = ''
        self.skey = ''
        self.pass_ticket = ''
        self.deviceid = 'e821100914705204'
        self.BaseRequest = {}
        self.ContactList = []
        self.My = []
        self.SyncKey = ''
        self.SyncKeyOrigin = {}
        self.Friends = []
        self.PublicAccount = []
        self.PublicAccountUsername = {}
        self.GroupChat = []
        self.Account = []
        self.UserToRemark = {}
        self.t1 = threading.Thread(target=self.thread)  # 监视消息端口线程
        self.t2 = threading.Thread(target=self.SendMsgThread)  # 发送信息线程

    # 获取二维码要用的uuid
    def GetUUID(self):
        # 参数列表
        param = {"appid": "wx782c26e4c19acffb",
                 "redirect_uri": "https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxnewloginpage",
                 "fun": "new",
                 "lang": "zh_CN",
                 "_": int(time.time())}
        # 获取uuid的api地址
        url = "https://login.wx2.qq.com/jslogin?"
        # get该地址，用session就是为了更加方便的保存自己的cookie数据
        resp = self.session.get(url, params=param, headers=self.headers)
        soup = BeautifulSoup(resp.content, "lxml")
        # 获得返回内容
        content = soup.get_text()
        # 预处理返回内容
        content = content.replace(" ", "").replace("\"", "")
        content = content[:-1]
        # 这里偷了个懒，用切片了，没用正则表达式
        dict = {}
        print(content)
        for item in content.split(";"):
            dict[item[:19]] = item[20:]
        if dict["window.QRLogin.code"] == "200":
            self.UUID = dict["window.QRLogin.uuid"]

    # 获取二维码
    def GetQRCore(self):
        url = "https://login.weixin.qq.com/qrcode/" + self.UUID
        resp = self.session.get(url, headers=self.headers)
        # 状态码为200时就下载图片到项目目录中
        if resp.status_code == 200:
            with open("./QRCore.jpg", "wb") as f:
                f.write(resp.content)
                f.close()
            # 打开该图片
            os.startfile("QRCore.jpg")

    # 监视端口判断是否扫码登录
    def MonitorPort(self):
        param = {
            "tip": self.tip,
            "uuid": self.UUID,
            "_": int(time.time() * 1000),
            "loginicon": "true"
        }
        url = "https://login.wx2.qq.com/cgi-bin/mmwebwx-bin/login?"
        resp = self.session.get(url, params=param, headers=self.headers)
        # 用BeautifulSoup4处理返回的数据
        soup = BeautifulSoup(resp.content, "lxml")
        content = soup.get_text()
        # split是把一个str以特定字符为分割切开几个部分,返回list
        WindowCode = content.split(";")[0].split("=")[1]
        if WindowCode == '201':  # 已扫码，修改tip为1再请求
            self.tip = 1
        elif WindowCode == '200':  # 已确认登录，获取重定向url
            self.redirect_url = content.split(';')[1].split('"')[1] + "&fun=new"
        elif WindowCode == '408':  # 超时
            print('超时')
            exit(1)
        return WindowCode

    # 获取登录信息
    def LoginIn(self):
        resp = self.session.get(self.redirect_url, headers=self.headers)
        # 返回一个xml表，需要获取其数据
        soup = BeautifulSoup(resp.content, "xml")
        # 是时候给 初始化的数据 赋值了
        self.wxsid = soup.wxsid.get_text()
        self.skey = soup.skey.get_text()
        self.wxuin = soup.wxuin.get_text()
        self.pass_ticket = soup.pass_ticket.get_text()
        # 判断获取的数据不为空
        if not all((self.skey, self.wxsid, self.wxuin, self.pass_ticket)):
            return False
        # 组建参数，后面有大用
        self.BaseRequest = {
            'Uin': int(self.wxuin),
            'Sid': self.wxsid,
            'Skey': self.skey,
            'DeviceID': self.deviceid
        }
        return True

    # 初始化
    def webwxinit(self):
        url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxinit?pass_ticket=%s&skey=%s&r=%s' % (
            self.pass_ticket, self.skey, int(time.time() * 1000))
        # 再封一层BaseRequest
        param = {
            'BaseRequest': self.BaseRequest
        }
        # 请求头内容类型
        h = self.headers;
        h['ContentType'] = 'application/json; charset=UTF-8'
        # 将数据封装到json
        resp = self.session.post(url, data=json.dumps(param), headers=h)
        data = resp.content.decode('utf-8')
        # 将返回的数据用json解码
        dict = json.loads(data)
        self.ContactList = dict['ContactList']
        self.My = dict['User']
        # 增加自己的Username来匹配名字
        self.UserToRemark[self.My['UserName']] = self.My['NickName']
        # 获取原汁原味的SyncKey，后续请求食用
        self.SyncKeyOrigin = dict['SyncKey']
        # 加工SyncKey
        SyncKey = []
        for i in dict['SyncKey']['List']:
            SyncKey.append("%s_%s" % (i['Key'], i['Val']))
        self.SyncKey = '|'.join(SyncKey)
        # 获取ErrMsg
        ErrMsg = dict['BaseResponse']['ErrMsg']
        # 获取Ret状态  0正常、1100异常
        Ret = dict['BaseResponse']['Ret']
        if Ret != 0:
            return False
        return True

    # 发送请求并根据返回码判断是否有新消息
    def SyncCheck(self):
        url = 'https://webpush.wx2.qq.com/cgi-bin/mmwebwx-bin/synccheck?' \
              'r=%s' \
              '&skey=%s' \
              '&sid=%s' \
              '&uin=%s' \
              '&deviceid=%s' \
              '&synckey=%s' \
              '&_=%s' % (int(time.time() * 1000), self.skey, self.wxsid, self.wxuin, self.deviceid, self.SyncKey,
                         int(time.time() * 1000))
        # 获取返回信息，当有语音连入时好像会返回乱码，所以要强制中断
        try:
            resp = self.session.get(url)
        except requests.exceptions.ConnectionError:
            print('好像有语音连入中，返回有误！正在重试...')
            return
        data = resp.content.decode('utf-8')
        # 正则表达式获取状态码与新消息码
        pattern = r'retcode:"(\d+)",selector:"(\d+)"'
        obj = re.search(pattern, data)
        retcode = obj.group(1)
        selector = obj.group(2)
        # 换行
        # print()
        # print(time.strftime("%H:%M:%S", time.localtime(time.time())) + "  " + retcode + '  ' + selector)
        if retcode == '0' and selector == '2':
            self.Sync()
        elif retcode == '1101':
            print('会话已超时！%s' % retcode)
            exit(1)

    # 获取新消息并更新SyncKey
    def Sync(self):
        url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsync?' \
              'sid=%s' \
              '&skey=%s' \
              '&lang=zh_CN' % (self.wxsid, self.skey)
        param = {
            'BaseRequest': self.BaseRequest,
            'SyncKey': self.SyncKeyOrigin,
            'rr': int(time.time())
        }
        h = self.headers
        h['ContentType'] = 'application/json; charset=UTF-8'
        resp = self.session.post(url, data=json.dumps(param), headers=h)
        data = resp.content.decode('utf-8')
        data = json.loads(data)

        if data['AddMsgCount'] == 1:
            # 记录from to信息以及内容
            content = data['AddMsgList'][0]['Content']
            FromUserName = data['AddMsgList'][0]['FromUserName']
            ToUserName = data['AddMsgList'][0]['ToUserName']
            RemarkName = self.UserToRemark.get(FromUserName, FromUserName)
            # 正则表达式获取群聊信息 群Username:群员Username:<br/>聊天内容
            if '@@' in FromUserName:
                pattern = '(.+):<br/>(.+)'
                obj = re.search(pattern, content)
                name = self.UserToRemark.get(obj.group(1), obj.group(1))
                content = obj.group(2)
                print('（群消息）' + RemarkName + ':\n' + '（群消息）' + name + ':' + content)
            # 忽视公众号消息
            elif FromUserName in self.PublicAccountUsername:
                print('（收到公众号推送） from：' + self.PublicAccountUsername[FromUserName])
            # 好友消息
            else:
                print(RemarkName + ":" + content)

        # 更新SyncKey
        SyncKey = []
        self.SyncKeyOrigin = data['SyncCheckKey']
        for i in data['SyncCheckKey']['List']:
            SyncKey.append("%s_%s" % (i['Key'], i['Val']))
        self.SyncKey = '|'.join(SyncKey)

        if data['AddMsgCount'] == 1:
            # 标识已阅读新消息
            self.notify(FromUserName, ToUserName)

    # 标记新消息已读
    def notify(self, FromUserName, ToUserName):
        # 标识已阅读新消息
        url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxstatusnotify?' \
              'lang=zh_CN' \
              '&pass_ticket=%s' % (self.pass_ticket)
        # 下面参数的From和To是颠倒了的，是个坑
        param = {
            'BaseRequest': self.BaseRequest,
            'ClientMsgId': int(time.time() * 1000),
            'Code': 1,
            'FromUserName': ToUserName,
            'ToUserName': FromUserName
        }
        h = self.headers;
        h['ContentType'] = 'application/json; charset=UTF-8'
        resp = self.session.post(url, data=json.dumps(param), headers=h)
        # 下面再申请一次Sync是因为网页端也有一次同步，模拟出来的操作
        self.Sync()

    # 新建一个线程监视消息端口
    def thread(self):
        while True:
            self.SyncCheck()

    # 获取联系人信息
    def GetContact(self):
        url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxgetcontact?' \
              'lang=zh_CN' \
              '&r=%s' \
              '&seq=0' \
              '&skey=%s' % (int(time.time() * 1000), self.skey)
        resp = self.session.get(url, headers=self.headers)
        data = resp.content.decode('utf-8')
        data = json.loads(data)
        if data['BaseResponse']['Ret'] != 0:
            print('获取联系人列表失败！')
            return False
        # 将相关联系人属性添加到属性中
        for member in data['MemberList']:
            if member['VerifyFlag'] != 0:  # 公众号的VerifyFlag一般是8的倍数
                self.PublicAccount.append(member)
                self.PublicAccountUsername['UserName'] = member['NickName']
            elif "@@" in member['UserName']:  # 群聊的Username有两个@
                self.GroupChat.append(member)
                self.UserToRemark[member['UserName']] = \
                    member['RemarkName'] if member['RemarkName'] != "" else member['NickName']
            else:  # 联系人的Username只有一个@
                self.Friends.append(member)
                self.UserToRemark[member['UserName']] = \
                    member['RemarkName'] if member['RemarkName'] != "" else member['NickName']
        return True

    # 发送消息功能
    def Sendmsg(self, ToUserName):
        url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsg?' \
              'lang=zh_CN' \
              '&pass_ticket=%s' % (self.pass_ticket)
        content = input("请输入要发送的消息：")
        # 前十三位为时间戳，后四位为随机数
        ID = str(int(time.time() * 1000)) + str(random.randint(1000, 9999))
        param = {
            'BaseRequest': self.BaseRequest,
            'Msg': {
                'ClientMsgId': ID,
                'Content': content,
                'FromUserName': self.My['UserName'],
                'LocalID': ID,
                'ToUserName': ToUserName,
                'Type': 1
            },
            'Scene': 0
        }
        h = self.headers
        h['ContentType'] = 'application/json; charset=UTF-8'
        # 由于json会自动用ascii编码，会让发送出去的字体变成代码，所以需要重新编码
        parm=json.dumps(param,ensure_ascii=False).encode('utf-8')
        resp = self.session.post(url, data=parm, headers=h)
        data = resp.content.decode('utf-8')
        data = json.loads(data)
        Ret = data['BaseResponse']['Ret']
        if Ret == 0:
            print('发送成功！')

    # 展示联系人，以及选择相关联系人发送消息
    def PrintToSentMsg(self):
        list = []
        select = int(input('1.联系人\n2.群聊\n3.公众号\n选择要发送的类别：'))
        # 三目嵌套来选择要遍历的list
        selector = self.Friends if select == 1 else (self.GroupChat if select == 2 else self.PublicAccount)
        count = 1
        for item in selector:
            Name = item['RemarkName'] if item['RemarkName'] != '' else item['NickName']
            print(str(count) + '.' + Name)
            list.append(item['UserName'])
            count+=1
        select = int(input('选择联系人编号以发送消息：'))
        self.Sendmsg(list[select - 1])

    def SendMsgThread(self):
        while True:
            self.PrintToSentMsg()

    def main(self):
        self.GetUUID()
        self.GetQRCore()
        while self.MonitorPort() != '200':
            time.sleep(1)
        os.remove('QRCore.jpg')
        if not self.LoginIn():
            print('登录失败')
            exit(1)
        if not self.webwxinit():
            print('初始化失败')
            exit(1)
        while not self.GetContact():
            print('获取联系人信息失败，正在重试...')
        self.t1.start()
        self.t2.start()


if __name__ == '__main__':
    wx = Login()
    wx.main()
