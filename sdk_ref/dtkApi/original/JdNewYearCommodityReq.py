# -*- coding:utf8-*-
"""
京东年货节商品
  @pageSize	Number	必须	每页返回条数，每页条数支持输入10,20，50,100。默认50条
  @pageId	String	必须	分页id：常规分页方式，请直接传入对应页码（比如：1,2,3……）
  @cids	String	非必须	大淘客的一级分类id，如果需要传多个，以英文逗号相隔，如：”1,2,3”。
  @sort	String	必须	排序方式，默认为0，0-综合排序，5-价格（券后价）从高到低，6-价格（券后价）从低到高

"""
from dtkApi.apiRequest import Request


class JdNewYearCommodityReq(Request):
    url = 'goods/jd-one-dollar-purchase'
    check_params = ['pageSize','pageId','sort']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, skuId, offsetDays=None):
        self.addParams('skuId', skuId)
        self.addParams('offsetDays', offsetDays)
