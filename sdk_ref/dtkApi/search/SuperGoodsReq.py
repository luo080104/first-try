# -*- coding:utf8-*-

"""
超级搜索
  @type	Number	必须	搜索类型：0-综合结果，1-大淘客商品，2-联盟商品
  @pageId	Number	必须	请求的页码，默认参数1
  @pageSize	Number	必须	每页条数，默认为20，最大值100
  @keyWords	string	必须	关键词搜索
  @tmall	Number	非必须	是否天猫商品：1-天猫商品，0-所有商品，不填默认为0
  @haitao	Number	非必须	是否海淘商品：1-海淘商品，0-所有商品，不填默认为0
  @sort	Number	非必须	排序字段信息 销量（total_sales） 价格（price），排序_des（降序），排序_asc（升序），示例：升序查询销量total_sales_asc 新增排序字段和排序方式，默认为0，0-综合排序，1-销量从高到低，2-销量从低到高，3-佣金比例从低到高，4-佣金比例从高到低，5-价格从高到低，6-价格从低到高(2021/1/15新增字段，之前的排序方式也可以使用)
  @specialId	string	非必须	会员运营id
  @channelId	string	非必须	渠道id将会和传入的pid进行验证，验证通过将正常转链，请确认填入的渠道id是正确的channelId对应联盟的relationId
  @priceLowerLimit	string	非必须	商品券后价下限(2021/1/15新增字段)
  @priceUpperLimit	string	非必须	商品券后价上限(2021/1/15新增字段)
  @endTkRate	string	非必须	淘客佣金比率上限(2021/1/15新增字段)
  @startTkRate	string	非必须	淘客佣金比率下限(2021/1/15新增字段)
  @hasCoupon	string	非必须	是否有券，1为有券，默认为全部(2021/1/15新增字段)
  @activityId string 非必须 多个使用,分隔符。示例：1,2,3

"""
from dtkApi.apiRequest import Request


class SuperGoodsReq(Request):
    url = 'goods/list-super-goods'
    check_params = ['pageId','pageSize','type','keyWords']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, type, pageId, pageSize, keyWords, tmall=None, haitao=None, sort=None, specialId=None,
                  channelId=None, priceLowerLimit=None, priceUpperLimit=None, endTkRate=None, startTkRate=None,
                  hasCoupon=None,activityId=None):
        self.addParams('type', type)
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('keyWords', keyWords)
        self.addParams('tmall', tmall)
        self.addParams('haitao', haitao)
        self.addParams('sort', sort)
        self.addParams('specialId', specialId)
        self.addParams('channelId', channelId)
        self.addParams('priceLowerLimit', priceLowerLimit)
        self.addParams('priceUpperLimit', priceUpperLimit)
        self.addParams('endTkRate', endTkRate)
        self.addParams('startTkRate', startTkRate)
        self.addParams('hasCoupon', hasCoupon)
        self.addParams('activityId', activityId)
