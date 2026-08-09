# -*- coding:utf8-*-
"""
失效商品
  @pageSize	Number	非必须	每页条数，默认为100，最大值200，若小于10，则按10条处理，每页条数仅支持输入10,50,100,200
  @pageId	String	必须	分页id，默认为1，支持传统的页码分页方式和scroll_id分页方式，根据用户自身需求传入值。示例1：商品入库，则首次传入1，后续传入接口返回的pageid，接口将持续返回符合条件的完整商品列表，该方式可以避免入口商品重复；示例2：根据pagesize和totalNum计算出总页数，按照需求返回指定页的商品（该方式可能在临近页取到重复商品） 建议方式：第一页的时候，pegeId传1，当请求后会返回pageId字符串，第二页一直到后面的所有翻页都使用这个pageId的字符串就可以了
  @startTime	String	非必须	开始时间，默认为yyyy-mm-dd hh:mm:ss，商品下架的时间大于等于开始时间，开始时间需要在当日
  @endTime	String	非必须	结束时间，默认为请求的时间，商品下架的时间小于等于结束时间，结束时间需要在当日
"""
from dtkApi.apiRequest import Request


class StaleGoodsByTimeReq(Request):
    url = 'goods/get-stale-goods-by-time'
    check_params = ['pageId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId,pageSize=None, startTime=None, endTime=None):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
        self.addParams('startTime', startTime)
        self.addParams('endTime', endTime)
