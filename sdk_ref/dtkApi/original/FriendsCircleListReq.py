# -*- coding:utf8-*-

"""
朋友圈文案
  @pageSize	Number	非必须	每页条数，默认为100，若小于10，则按10条处理，每页条数仅支持输入10,50,100
  @pageId	String	必须	分页id，默认为1，支持传统的页码分页方式
  @sort	String	非必须	排序方式，默认为0，0-综合排序，1-商品上架时间从高到低，2-销量从高到低，3-领券量从高到低，4-佣金比例从高到低，5-价格（券后价）从高到低，6-价格（券后价）从低到高
  @cid	String	非必须	大淘客的一级分类id，如6、4
  @subcid	String	非必须	大淘客的二级类目id，通过超级分类API获取。仅允许传一个二级id，当一级类目id和二级类目id同时传入时，会自动忽略二级类目id
  @pre	Number	非必须	是否预告商品，1-预告商品，0-所有商品，不填默认为0
  @freeshipRemoteDistrict	Number	非必须	偏远地区包邮，1-是，0-非偏远地区，不填默认所有商品
  @goodsId	Number	非必须	大淘客id或淘宝id，查询单个商品是否有朋友圈文案，如果有，则返回商品信息及朋友圈文案，如果没有，显示10006错误

"""
from dtkApi.apiRequest import Request


class FriendsCircleListReq(Request):
    url = 'goods/friends-circle-list'
    check_params = ['pageId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId,pageSize=None, sort=None, cid=None, subcid=None, pre=None, freeshipRemoteDistrict=None,
                  goodsId=None):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
        self.addParams('sort', sort)
        self.addParams('cid', cid)
        self.addParams('subcid', subcid)
        self.addParams('pre', pre)
        self.addParams('freeshipRemoteDistrict', freeshipRemoteDistrict)
        self.addParams('goodsId', goodsId)

