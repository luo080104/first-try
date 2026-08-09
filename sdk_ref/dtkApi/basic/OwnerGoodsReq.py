# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
淘宝商品
我发布的商品
  @pageId	String	必须	分页id，默认为1，支持传统的页码分页方式和scroll_id分页方式，根据用户自身需求传入值。示例1：商品入库，则首次传入1，后续传入接口返回的pageid，接口将持续返回符合条件的完整商品列表，该方式可以避免入口商品重复；示例2：根据pagesize和totalNum计算出总页数，按照需求返回指定页的商品（该方式可能在临近页取到重复商品）
  @pageSize	Number	必须	每页条数，默认为100，最大值200，若小于10，则按10条处理，每页条数仅支持输入10,50,100,200
  @online	Number	非必须	是否下架，默认为1,1-未下架商品，0-已下架商品
  @startTime	Date	非必须	商品提交开始时间，请求格式：yyyy-MM-dd HH:mm:ss
  @endTime	Date	非必须	商品上架结束时间，请求格式：yyyy-MM-dd HH:mm:ss
  @sort	String	非必须	排序字段，默认为0，0-综合排序，1-商品上架时间从新到旧，2-销量从高到低，3-领券量从高到低，4-佣金比例从高到低，5-价格（券后价）从高到低，6-价格（券后价）从低到高

"""


class OwnerGoodsReq(Request):
    url = 'goods/get-owner-goods'
    check_params = ['pageId','pageSize']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId, pageSize, online=None, startTime=None, endTime=None, sort=None):
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('online', online)
        self.addParams('startTime', startTime)
        self.addParams('endTime', endTime)
        self.addParams('sort', sort)

