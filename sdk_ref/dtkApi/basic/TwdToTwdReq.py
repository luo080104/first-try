# -*- coding:utf8-*-

"""
淘口令转淘口令
  @content	string	必须	支持包含文本的淘口令，但最好是一个单独淘口令
  @pid	string	非必须	推广位ID，用户可自由填写当前大淘客账号下已授权淘宝账号的任一pid，若未填写，则默认使用创建应用时绑定的pid
  @channelId	string	非必须	渠道id将会和传入的pid进行验证，验证通过将正常转链，请确认填入的渠道id是正确的
  @special_id	string	非必须	会员运营ID
  @external_id	string	非必须	淘宝客外部用户标记，如自身系统账户ID；微信ID等
"""
from dtkApi.apiRequest import Request


class TwdToTwdReq(Request):
    url = 'tb-service/twd-to-twd'
    check_params = ['content']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, content, pid=None, channelId=None, special_id=None, external_id=None):
        self.addParams('content', content)
        self.addParams('pid', pid)
        self.addParams('channelId', channelId)
        self.addParams('special_id', special_id)
        self.addParams('external_id', external_id)
