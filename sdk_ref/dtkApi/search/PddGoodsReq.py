# -*- coding:utf8-*-

"""
拼多多联盟搜索
  @activityTags	String	否	活动商品标记数组，例：[4,7]， 4-秒杀，7-百亿补贴，31-品牌黑标，10564-精选爆品-官方直推爆款，10584-精选爆品-团长推荐， 24-品牌高佣，20-行业精选，21-金牌商家，10044-潜力爆品，10475-爆品上新，其他的值请忽略
  @blockCats	String	否	自定义屏蔽一级/二级/三级类目ID，自定义数量不超过20个;
  @blockCatPackages	String	否	屏蔽商品类目包：1-拼多多小程序屏蔽的类目&关键词;2-虚拟类目;3-医疗器械;4-处方药;5-非处方药
  @catId	Number	否	商品类目ID
  @goodsSignList	String	否	商品goodsSign列表 访问括号内链接可查看字段相关说明(http://www.dataoke.com/kfpt/open-gz.html?id=100)
  @isBrandGoods	Integer	否	是否为品牌商品
  @keyword	String	否	商品关键词(暂不支持goodid进行搜索，如需定向搜索商品建议使用goodsign进行搜索)
  @listId	String	否	翻页时建议填写前页返回的list_id值
  @merchantTypeList	String	否	店铺类型数组 1-个人，2-企业，3-旗舰店，4-专卖店，5-专营店，6-普通店（未传为全部）
  @optId	Number	否	商品标签类目ID
  @page	Integer	否	默认值1，商品分页数
  @pageSize	Integer	否	默认100，每页商品数量
  @rangeList	String	否	筛选范围列表 样例：[{"range_id":0,"range_from":1,"range_to":1500}, {"range_id":1,"range_from":1,"range_to":1500}]
  @sortType	Integer	否	排序方式:0-综合排序;2-按佣金比例降序;3-按价格升序;4-按价格降序;6-按销量降序;9-券后价升序排序;10-券后价降序排序;16-店铺描述评分降序
  @withCoupon	Integer	否	是否只返回优惠券的商品，0返回所有商品，1只返回有优惠券的商品
  @withCategoryInfo Integer 非必须 是否返回分类信息数据 0-否；1-是

"""
from dtkApi.apiRequest import Request


class PddGoodsReq(Request):
    url = 'dels/pdd/goods/search'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, activityTags=None, blockCats=None, blockCatPackages=None, catId=None, goodsSignList=None,
                  isBrandGoods=None, keyword=None, listId=None, merchantTypeList=None, optId=None, page=None,
                  pageSize=None, rangeList=None, sortType=None, withCoupon=None,withCategoryInfo=None):
        self.addParams('activityTags', activityTags)
        self.addParams('blockCats', blockCats)
        self.addParams('blockCatPackages', blockCatPackages)
        self.addParams('catId', catId)
        self.addParams('goodsSignList', goodsSignList)
        self.addParams('isBrandGoods', isBrandGoods)
        self.addParams('keyword', keyword)
        self.addParams('listId', listId)
        self.addParams('merchantTypeList', merchantTypeList)
        self.addParams('optId', optId)
        self.addParams('page', page)
        self.addParams('pageSize', pageSize)
        self.addParams('rangeList', rangeList)
        self.addParams('sortType', sortType)
        self.addParams('withCoupon', withCoupon)
        self.addParams('withCategoryInfo', withCategoryInfo)

