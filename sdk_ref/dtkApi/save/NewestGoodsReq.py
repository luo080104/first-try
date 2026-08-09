# -*- coding:utf8-*-

"""
商品更新
  @pageId	String	必须	分页id，默认为1，支持传统的页码分页方式和scroll_id分页方式，根据用户自身需求传入值。示例1：商品入库，则首次传入1，后续传入接口返回的pageid，接口将持续返回符合条件的完整商品列表，该方式可以避免入口商品重复；示例2：根据pagesize和totalNum计算出总页数，按照需求返回指定页的商品（该方式可能在临近页取到重复商品）
  @pageSize	Number	必须	每页条数，默认为100，最大值200，若小于10，则按10条处理，每页条数仅支持输入10,50,100,200
  @startTime	Date	非必须	商品上架开始时间，请求格式：yyyy-MM-dd HH:mm:ss
  @endTime	Date	非必须	商品上架结束时间，请求格式：yyyy-MM-dd HH:mm:ss
  @cids	String	非必须	大淘客的一级分类id，如果需要传多个，以英文逗号相隔，如：”1,2,3”。当一级类目id和二级类目id同时传入时，会自动忽略二级类目id，1 -女装，2 -母婴，3 -美妆，4 -居家日用，5 -鞋品，6 -美食，7 -文娱车品，8 -数码家电，9 -男装，10 -内衣，11 -箱包，12 -配饰，13 -户外运动，14 -家装家纺
  @subcid	Number	非必须	大淘客的二级类目id，通过超级分类API获取。仅允许传一个二级id，当一级类目id和二级类目id同时传入时，会自动忽略二级类目id
  @juHuaSuan	Number	非必须	1-聚划算商品，0-所有商品，不填默认为0
  @taoQiangGou	Number	非必须	1-淘抢购商品，0-所有商品，不填默认为0
  @tmall	Number	非必须	1-天猫商品，0-非天猫商品，不填默认全部商品
  @tchaoshi	Number	非必须	1-天猫超市商品，0-所有商品，不填默认为0
  @goldSeller	Number	非必须	1-金牌卖家，0-所有商品，不填默认为0
  @haitao	Number	非必须	1-海淘，0-所有商品，不填默认为0
  @brand	Number	非必须	1-品牌，0-所有商品，不填默认为0
  @brandIds	String	非必须	品牌id，当brand传入0时，再传入brandIds将获取不到结果。品牌id可以传多个，以英文逗号隔开，如：”345,321,323”
  @preSale	Number	非必须	1-活动预售商品，0-所有商品，不填默认为0。（2020.10.30号新增字段）
  @priceLowerLimit	Number	非必须	价格（券后价）下限
  @priceUpperLimit	Number	非必须	价格（券后价）上限
  @couponPriceLowerLimit	Number	非必须	最低优惠券面额
  @commissionRateLowerLimit	Number	非必须	最低佣金比率
  @monthSalesLowerLimit	Number	非必须	最低月销量
  @sort	String	非必须	排序字段，默认为0，0-综合排序，1-商品上架时间从新到旧，2-销量从高到低，3-领券量从高到低，4-佣金比例从高到低，5-价格（券后价）从高到低，6-价格（券后价）从低到高

"""
from dtkApi.apiRequest import Request


class NewestGoodsReq(Request):
    url = 'goods/get-newest-goods'
    check_params = ['pageId','pageSize']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId, pageSize, startTime=None, endTime=None, cids=None, subcid=None, juHuaSuan=None,
                  taoQiangGou=None, tmall=None, tchaoshi=None, goldSeller=None, haitao=None, brand=None, brandIds=None,
                  preSale=None, priceLowerLimit=None, priceUpperLimit=None, couponPriceLowerLimit=None,
                  commissionRateLowerLimit=None, monthSalesLowerLimit=None, sort=None):
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('startTime', startTime)
        self.addParams('endTime', endTime)
        self.addParams('cids', cids)
        self.addParams('subcid', subcid)
        self.addParams('juHuaSuan', juHuaSuan)
        self.addParams('taoQiangGou', taoQiangGou)
        self.addParams('tmall', tmall)
        self.addParams('tchaoshi', tchaoshi)
        self.addParams('goldSeller', goldSeller)
        self.addParams('haitao', haitao)
        self.addParams('brand', brand)
        self.addParams('brandIds', brandIds)
        self.addParams('preSale', preSale)
        self.addParams('priceLowerLimit', priceLowerLimit)
        self.addParams('priceUpperLimit', priceUpperLimit)
        self.addParams('couponPriceLowerLimit', couponPriceLowerLimit)
        self.addParams('commissionRateLowerLimit', commissionRateLowerLimit)
        self.addParams('monthSalesLowerLimit', monthSalesLowerLimit)
        self.addParams('sort', sort)
