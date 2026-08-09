# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
拼多多商品转链
 @pid String 必须  拼多多推广位id
 @goodsSign String 必须  商品goodsSign 访问括号内链接可查看字段相关说明(http://www.dataoke.com/kfpt/open-gz.html?id=100)
 @customParameters String 非必须  自定义参数，为链接打上自定义标签； 自定义参数最长限制64个字节； 格式为： {"uid":"11111","sid":"22222"} ， 其中 uid 用户唯一标识，可自行加密后传入， 每个用户仅且对应一个标识，必填； sid 上下文信息标识，例如sessionId等， 非必填。该json字符串中也可以加入其他自定义的key In
 @zsDuoId String 非必须 招商多多客ID
"""


class PddGoodsLinkReq(Request):
    url = 'dels/pdd/kit/goods-prom-generate'
    check_params = ['pid','goodsSign']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pid,goodsSign,customParameters=None,zsDuoId=None):
        self.addParams('pid', pid)
        self.addParams('goodsSign', goodsSign)
        self.addParams('customParameters', customParameters)
        self.addParams('zsDuoId', zsDuoId)
