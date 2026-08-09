# -*- coding:utf8-*-
"""
每日爆品推荐
  @pageId	String	必须	分页id：常规分页方式，请直接传入对应页码（比如：1,2,3……）
  @pageSize	Number	必须	每页返回条数，每页条数支持输入10,20，50,100。默认50条
  @PriceCid	String	非必须	价格区间，1表示10~20元区；2表示20~40元区；3表示40元以上区；默认为1
  @cids	String	非必须	大淘客的一级分类id，如果需要传多个，以英文逗号相隔，如：”1,2,3”。1 -女装，2 -母婴，3 -美妆，4 -居家日用，5 -鞋品，6 -美食，7 -文娱车品，8 -数码家电，9 -男装，10 -内衣，11 -箱包，12 -配饰，13 -户外运动，14 -家装家纺。不填默认全部
"""
from dtkApi.apiRequest import Request


class ExplosiveGoodsListReq(Request):
    url = 'goods/explosive-goods-list'
    check_params = ['pageId','pageSize']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId, pageSize,cids=None, PriceCid=None):
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('PriceCid', PriceCid)
        self.addParams('cids', cids)
