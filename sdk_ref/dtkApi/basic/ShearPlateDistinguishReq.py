# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
剪贴板识别
  @content	String	必须	文本内容
  @TbPid	String	非必须	淘宝联盟pid
  @TbChannelId	String	非必须	淘宝联盟渠道id
  @JdUnionId	Number	非必须	京东联盟unionId
  @JdPid	Number	非必须	京东联盟pid
  @PddPid	String	非必须	拼多多联盟pid
  @customerParameters	String	非必须	自定义参数，为链接打上自定义标签；自定义参数最长限制64个字节；格式为： {"uid":"11111","sid":"22222"} 其中 uid 用户唯一标识，可自行加密后传入，每个用户仅且对应一个标识，必填； sid 上下文信息标识，例如sessionId等，非必填。该json字符串中也可以加入其他自定义的key。（如果使用GET请求，请使用URLEncode处理参数）
"""


class ShearPlateDistinguishReq(Request):
    url = 'dels/kit/contentParse'
    check_params = ['content']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, content, TbPid=None, TbChannelId=None, JdUnionId=None, JdPid=None, PddPid=None,
                  customerParameters=None):
        self.addParams('content', content)
        self.addParams('TbPid', TbPid)
        self.addParams('TbChannelId', TbChannelId)
        self.addParams('JdUnionId', JdUnionId)
        self.addParams('JdPid', JdPid)
        self.addParams('PddPid', PddPid)
        self.addParams('customerParameters', customerParameters)
