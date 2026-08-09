# -*- coding:utf8-*-

"""
京东联盟搜索
  @cid1	Long	否	一级类目id
  @cid2	Long	否	二级类目id
  @cid3	Long	否	三级类目id
  @pageId	Integer	否	页码
  @pageSize	Integer	否	每页数量，单页数最大30，默认20
  @skuIds	String	否	skuid集合(一次最多支持查询100个sku)，多个使用“,”分隔符
  @keyword	String	否	关键词，字数同京东商品名称一致，目前未限制
  @priceFrom	BigDecimal	否	商品券后价格下限
  @priceTo	BigDecimal	否	商品券后价格上限
  @commissionShareStart	Integer	否	佣金比例区间开始
  @commissionShareEnd	Integer	否	佣金比例区间结束
  @owner	String	否	商品类型：自营[g]，POP[p]
  @sortName	String	否	排序字段(price：单价, commissionShare：佣金比例, commission：佣金， inOrderCount30Days：30天引单量， inOrderComm30Days：30天支出佣金)
  @sort	String	否	asc：升序；desc：降序。默认降序
  @isCoupon	Integer	否	是否是优惠券商品，1：有优惠券，0：无优惠券
  @pingouPriceStart	BigDecimal	否	拼购价格区间开始
  @pingouPriceEnd	BigDecimal	否	拼购价格区间结束
  @brandCode	String	否	品牌code
  @shopId	Integer	否	店铺Id
  @hasBestCoupon	Integer	否	1：查询有最优惠券商品；其他值过滤掉此入参条件。（查询最优券需与isCoupon同时使用）
  @pid	String	否	联盟id_应用iD_推广位id
  @jxFlags	String	否	京喜商品类型，1京喜、2京喜工厂直供、3京喜优选（包含3时可在京东APP购买），入参多个值表示或条件查询
  @spuId	Long	否	主商品spuId
  @couponUrl	String	否	优惠券链接
  @deliveryType	Integer	否	京东配送 1：是，0：不是

"""
from dtkApi.apiRequest import Request


class JdGoodsReq(Request):
    url = 'dels/jd/goods/search'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, cid1=None, cid2=None, cid3=None, pageId=None, pageSize=None, skuIds=None, keyword=None,
                  priceFrom=None, priceTo=None, commissionShareStart=None, commissionShareEnd=None, owner=None,
                  sortName=None, sort=None, isCoupon=None, pingouPriceStart=None, pingouPriceEnd=None, brandCode=None,
                  shopId=None, hasBestCoupon=None, pid=None, jxFlags=None, spuId=None, couponUrl=None,
                  deliveryType=None):
        self.addParams('cid1', cid1)
        self.addParams('cid2', cid2)
        self.addParams('cid3', cid3)
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('skuIds', skuIds)
        self.addParams('keyword', keyword)
        self.addParams('priceFrom', priceFrom)
        self.addParams('priceTo', priceTo)
        self.addParams('commissionShareStart', commissionShareStart)
        self.addParams('commissionShareEnd', commissionShareEnd)
        self.addParams('owner', owner)
        self.addParams('sortName', sortName)
        self.addParams('sort', sort)
        self.addParams('isCoupon', isCoupon)
        self.addParams('pingouPriceStart', pingouPriceStart)
        self.addParams('pingouPriceEnd', pingouPriceEnd)
        self.addParams('brandCode', brandCode)
        self.addParams('shopId', shopId)
        self.addParams('hasBestCoupon', hasBestCoupon)
        self.addParams('pid', pid)
        self.addParams('jxFlags', jxFlags)
        self.addParams('spuId', spuId)
        self.addParams('couponUrl', couponUrl)
        self.addParams('deliveryType', deliveryType)
