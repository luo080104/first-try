# -*- coding:utf8-*-
"""
定时拉取
  @pageSize	Number	非必须	每页条数，默认为100，最大值200，若小于10，则按10条处理，每页条数仅支持输入10,50,100,200
  @pageId	String	必须	分页id，默认为1，支持传统的页码分页方式和scroll_id分页方式，根据用户自身需求传入值。示例1：商品入库，则首次传入1，后续传入接口返回的pageid，接口将持续返回符合条件的完整商品列表，该方式可以避免入口商品重复；示例2：根据pagesize和totalNum计算出总页数，按照需求返回指定页的商品（该方式可能在临近页取到重复商品）
  @cid	String	非必须	大淘客的一级分类id。当一级类目id和二级类目id同时传入时，会自动忽略二级类目id
  @subcid	Number	非必须	大淘客的二级类目id，通过超级分类API获取。仅允许传一个二级id，当一级类目id和二级类目id同时传入时，会自动忽略二级类目id
  @pre	Number	非必须	是否预告商品，1-预告商品，0-所有商品，不填默认为0
  @sort	String	非必须	排序方式，默认为0，0-综合排序，1-商品上架时间从新到旧，2-销量从高到低，3-领券量从高到低，4-佣金比例从高到低，5-价格（券后价）从高到低，6-价格（券后价）从低到高
  @startTime	String	非必须	开始时间，格式为yyyy-mm-dd hh:mm:ss，商品上架的时间大于等于开始时间
  @endTime	String	非必须	结束时间，默认为请求的时间，商品上架的时间小于等于结束时间
  @freeshipRemoteDistrict	Number	非必须	偏远地区包邮，1-是，0-非偏远地区，不填默认所有商品
  @choice	Number	非必须	是否为精选商品，默认全部商品，1-精选商品（3.19新增字段）

"""
from dtkApi.apiRequest import Request


class GoodsByTimeReq(Request):
    url = 'goods/pull-goods-by-time'
    check_params = ['pageId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self,pageId, pageSize=None, cid=None, subcid=None, pre=None, sort=None, startTime=None, endTime=None,
                  freeshipRemoteDistrict=None, choice=None):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
        self.addParams('cid', cid)
        self.addParams('subcid', subcid)
        self.addParams('pre', pre)
        self.addParams('sort', sort)
        self.addParams('startTime', startTime)
        self.addParams('endTime', endTime)
        self.addParams('freeshipRemoteDistrict', freeshipRemoteDistrict)
        self.addParams('choice', choice)
