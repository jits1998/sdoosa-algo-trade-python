
class Order:
  def __init__(self, orderInputParams = None):
    self.tradingSymbol = orderInputParams.tradingSymbol if orderInputParams != None else ""
    self.exchange = orderInputParams.exchange if orderInputParams != None else "NSE"
    self.productType = orderInputParams.productType if orderInputParams != None else ""
    self.orderType = orderInputParams.orderType if orderInputParams != None else "" # LIMIT/MARKET/SL-LIMIT/SL-MARKET
    self.price = orderInputParams.price if orderInputParams != None else 0
    self.triggerPrice = orderInputParams.triggerPrice if orderInputParams != None else 0 # Applicable in case of SL orders
    self.qty = orderInputParams.qty if orderInputParams != None else 0
    self.tag = orderInputParams.tag if orderInputParams != None else None
    self.orderId = None # The order id received from broker after placing the order
    self.orderStatus = None # One of the status defined in ordermgmt.OrderStatus
    self.averagePrice = 0 # Average price at which the order is filled
    self.filledQty = 0 # Filled quantity
    self.pendingQty = 0 # Qty - Filled quantity
    self.orderPlaceTimestamp = None # Timestamp when the order is placed
    self.lastOrderUpdateTimestamp = None # Applicable if you modify the order Ex: Trailing SL
    self.message = None # In case any order rejection or any other error save the response from broker in this field
    self.parentOrderId = None
    
  def __str__(self):
    return "orderId=" + str(self.orderId) + ", orderStatus=" + str(self.orderStatus) \
      + ", symbol=" + str(self.tradingSymbol) + ", productType=" + str(self.productType) \
      + ", orderType=" + str(self.orderType) + ", price=" + str(self.price) \
      + ", triggerPrice=" + str(self.triggerPrice) + ", qty=" + str(self.qty) \
      + ", filledQty=" + str(self.filledQty) + ", pendingQty=" + str(self.pendingQty) \
      + ", averagePrice=" + str(self.averagePrice)
