# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
三合一红包
  @merchantType	Integer	必须	（1-淘宝红包，2京东红包，3-拼多多红包）
  @pid	String	否	推广位ID（大淘客账号下已授权淘宝账号的任一pid，若未填写，则默认使用创建应用时绑定的pid；其中京东pid为联盟子推客身份标识（不能传入接口调用者自己的pid）
  @unionId	String	非必须	选择京东红包时需要填入京东联盟ID（在京东联盟后台个人中心）。其他类型不用传

"""


class MergeRedEnvelopesReq(Request):
    url = 'dels/merge-red-envelopes'
    check_params = ['merchantType']
    second_check_params = ['unionId']


    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            if self.params['merchantType']==2:
                if self.check_args(self.params, self.second_check_params):
                    return self.request('GET', api_url=self.url, args=self.params)
            else:
                return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, merchantType,pid=None,unionId=None):
        self.addParams('merchantType', merchantType)
        self.addParams('pid', pid)
        self.addParams('unionId', unionId)
