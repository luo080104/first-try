# -*- coding:utf8-*-

"""
直播好货
  @date String 非必须 选择某一天的直播商品数据，默认返回全部参与过直播，且未下架的商品。时间格式：2020-09-16
  @sort String 非必须 排序方式，默认为0，0-综合排序，1-商品上架时间从高到低，2-销量从高到低，3-领券量从高到低，4-佣金比例从高到低，5-价格（券后价）从高到低，6-价格（券后价）从低到高
"""
from dtkApi.apiRequest import Request


class LiveMaterialGoodsListReq(Request):
    url = 'goods/liveMaterial-goods-list'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self,date=None, sort=None):
        self.addParams('date', date)
        self.addParams('sort', sort)
