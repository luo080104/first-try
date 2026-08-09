# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
京东商品转链
 @unionId	Long	必须	推客的联盟ID
 @materialId	String	必须	推广物料url，例如活动链接、商品链接等；不支持仅传入skuid
 @positionId	Long	非必须	新增推广位id （若无subUnionId权限，可入参该参数用来确定不同用户下单情况）
 @childPid	String	非必须	联盟子推客身份标识（不能传入接口调用者自己的pid）
 @subUnionId	String	非必须	子渠道标识，您可自定义传入字母、数字或下划线，最多支持80个字符，该参数会在订单行查询接口中展示，需要有权限才可使用
 @couponUrl	String	非必须	优惠券领取链接，在使用优惠券、商品二合一功能时入参，且materialId须为商品详情页链接（5.27更新：若不填则会自动匹配上全额最大的优惠券进行转链）
 @chainType	Integer	非必须	转链类型，默认短链，短链有效期60天1：长链2：短链 3：长链+短链，
 @giftCouponKey	String	非必须	礼金批次号
"""


class JdGoodsLinkReq(Request):
    url = 'dels/jd/kit/promotion-union-convert'
    check_params = ['unionId','materialId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, unionId, materialId, positionId=None, childPid=None, subUnionId=None, couponUrl=None,
                  chainType=None, giftCouponKey=None):
        self.addParams('unionId', unionId)
        self.addParams('materialId', materialId)
        self.addParams('positionId', positionId)
        self.addParams('childPid', childPid)
        self.addParams('subUnionId', subUnionId)
        self.addParams('couponUrl', couponUrl)
        self.addParams('chainType', chainType)
        self.addParams('giftCouponKey', giftCouponKey)