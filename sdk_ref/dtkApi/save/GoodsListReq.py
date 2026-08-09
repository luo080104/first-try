# -*- coding:utf8-*-

"""
商品列表
  @pageId	String	必须	默认为1，支持传统的页码分页方式和scroll_id分页方式，根据用户自身需求传入值。示例1：商品入库，则首次传入1，后续传入接口返回的pageid，接口将持续返回符合条件的完整商品列表，该方式可以避免入口商品重复；示例2：根据pagesize和totalNum计算出总页数，按照需求返回指定页的商品（该方式可能在临近页取到重复商品）
  @pageSize	Number	非必须	每页条数，默认为100，最大值200，若小于10，则按10条处理，每页条数仅支持输入10,50,100,200
  @sort	String	非必须	排序方式，默认为0，0-综合排序，1-商品上架时间从高到低，2-销量从高到低，3-领券量从高到低，4-佣金比例从高到低，5-价格（券后价）从高到低，6-价格（券后价）从低到高，7-券金额从高到底
  @cids	String	非必须	大淘客的一级分类id，如果需要传多个，以英文逗号相隔，如：”1,2,3”。当一级类目id和二级类目id同时传入时，会自动忽略二级类目id
  @subcid	Number	非必须	大淘客的二级类目id，通过超级分类API获取。仅允许传一个二级id，当一级类目id和二级类目id同时传入时，会自动忽略二级类目id
  @specialId	Number	非必须	商品卖点，1.拍多件活动；2.多买多送；3.限量抢购；4.额外满减；6.买商品礼赠
  @juHuaSuan	Number	非必须	1-聚划算商品，0-所有商品，不填默认为0
  @taoQiangGou	Number	非必须	1-淘抢购商品，0-所有商品，不填默认为0
  @tmall	Number	非必须	1-天猫商品， 0-非天猫商品，不填默认所有商品
  @tchaoshi	Number	非必须	1-天猫超市商品， 0-所有商品，不填默认为0
  @goldSeller	Number	非必须	1-金牌卖家商品，0-所有商品，不填默认为0
  @haitao	Number	非必须	1-海淘商品， 0-所有商品，不填默认为0
  @pre	Number	非必须	1-预告商品，0-所有商品，不填默认为0
  @preSale	Number	非必须	1-活动预售商品，0-所有商品，不填默认为0。（10.30新增字段）
  @brand	Number	非必须	1-品牌商品，0-所有商品，不填默认为0
  @brandIds	Number	非必须	当brand传入0时，再传入brandIds可能无法获取结果。品牌id可以传多个，以英文逗号隔开，如：”345,321,323”
  @priceLowerLimit	Number	非必须	价格（券后价）下限
  @priceUpperLimit	Number	非必须	价格（券后价）上限
  @couponPriceLowerLimit	Number	非必须	最低优惠券面额
  @commissionRateLowerLimit	Number	非必须	最低佣金比率
  @monthSalesLowerLimit	Number	非必须	最低月销量
  @freeshipRemoteDistrict	Number	非必须	偏远地区包邮，1-是，0-非偏远地区，不填默认所有商品
  @directCommissionType	Number	非必须	定向佣金类型，3查询定向佣金商品，否则查询全部商品（12.22新增字段）
  @choice	Number	非必须	是否为精选商品，默认全部，1-精选商品（3.19新增字段）
  @flagShipStore	Number	非必须	1-官方旗舰店商品，0-不限是否是旗舰店，不填默认为0（2021/10/11更新）
  @isNew	Number	非必须	1-30天新品，0-不限，不填默认为0（新品与最低价不能同时选，否则无商品）（2021/10/11更新）
  @lowestPrice	Number	非必须	1-30天最低价，0-不限，不填默认为0（新品与最低价不能同时选，否则无商品）（2021/10/11更新）
  @activityId string 非必须 多个使用,分隔符。示例：1,2,3
  @maxCouponAmount 非必须 最高优惠券面额 （2022/4/11更新）
  @maxCommissionRate 非必须 最高佣金比例 （2022/4/11更新）
"""
from dtkApi.apiRequest import Request


class GoodsListReq(Request):
    url = 'goods/get-goods-list'
    check_params=['pageId']
    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    # 设置传入参数
    def setParams(self, pageId, pageSize=None, sort=None, cids=None, subcid=None, specialId=None, juHuaSuan=None,
                  taoQiangGou=None, tmall=None, tchaoshi=None, goldSeller=None, haitao=None, pre=None, preSale=None,
                  brand=None, brandIds=None, priceLowerLimit=None, priceUpperLimit=None, couponPriceLowerLimit=None,
                  commissionRateLowerLimit=None, monthSalesLowerLimit=None, freeshipRemoteDistrict=None,
                  directCommissionType=None, choice=None, flagShipStore=None, isNew=None, lowestPrice=None,
                  activityId=None, maxCouponAmount=None, maxCommissionRate=None):
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('sort', sort)
        self.addParams('cids', cids)
        self.addParams('subcid', subcid)
        self.addParams('specialId', specialId)
        self.addParams('juHuaSuan', juHuaSuan)
        self.addParams('taoQiangGou', taoQiangGou)
        self.addParams('tmall', tmall)
        self.addParams('tchaoshi', tchaoshi)
        self.addParams('goldSeller', goldSeller)
        self.addParams('haitao', haitao)
        self.addParams('pre', pre)
        self.addParams('preSale', preSale)
        self.addParams('brand', brand)
        self.addParams('brandIds', brandIds)
        self.addParams('priceLowerLimit', priceLowerLimit)
        self.addParams('priceUpperLimit', priceUpperLimit)
        self.addParams('couponPriceLowerLimit', couponPriceLowerLimit)
        self.addParams('commissionRateLowerLimit', commissionRateLowerLimit)
        self.addParams('monthSalesLowerLimit', monthSalesLowerLimit)
        self.addParams('freeshipRemoteDistrict', freeshipRemoteDistrict)
        self.addParams('directCommissionType', directCommissionType)
        self.addParams('choice', choice)
        self.addParams('flagShipStore', flagShipStore)
        self.addParams('isNew', isNew)
        self.addParams('lowestPrice', lowestPrice)
        self.addParams('activityId', activityId)
        self.addParams('maxCouponAmount', maxCouponAmount)
        self.addParams('maxCommissionRate', maxCommissionRate)