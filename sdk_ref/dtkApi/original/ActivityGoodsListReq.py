# -*- coding:utf8-*-

"""
活动商品
  @pageId	String	必须	分页id，默认为1，支持传统的页码分页方式和scroll_id分页方式，根据用户自身需求传入值。示例1：商品入库，则首次传入1，后续传入接口第一次返回的pageid，接口将持续返回符合条件的完整商品列表，该方式可以避免入库商品重复；示例2：根据pagesize和totalNum计算出总页数，按照需求返回指定页的商品（该方式可能在临近页取到重复商品）
  pageSize	Number	非必须	每页条数，默认为100，大于100按100处理
  activityId	Number	必须	通过热门活动API获取的活动id
  cid	Number	非必须	大淘客一级分类ID：1 -女装，2 -母婴，3 -美妆，4 -居家日用，5 -鞋品，6 -美食，7 -文娱车品，8 -数码家电，9 -男装，10 -内衣，11 -箱包，12 -配饰，13 -户外运动，14 -家装家纺
  subcid	Number	非必须	大淘客二级分类ID：可通过超级分类接口获取二级分类id，当同时传入一级分类id和二级分类id时，以一级分类id为准
  freeshipRemoteDistrict	Number	非必须	偏远地区包邮：1.是，0.否

"""
from dtkApi.apiRequest import Request


class ActivityGoodsListReq(Request):
    url = 'goods/activity/goods-list'
    check_params = ['pageId','activityId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId,activityId, pageSize=None, cid=None, subcid=None, freeshipRemoteDistrict=None):
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('activityId', activityId)
        self.addParams('cid', cid)
        self.addParams('subcid', subcid)
        self.addParams('freeshipRemoteDistrict', freeshipRemoteDistrict)
