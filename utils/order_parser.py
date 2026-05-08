"""
单号前缀解析与验证。
"""


def classify_order(order_id: str) -> str:
    """判断单号类型。

    :param order_id: 单号字符串
    :return: 'T' (订单ID), 'S' (服务单ID), 'INVALID' (非法)
    """
    if not order_id or not isinstance(order_id, str):
        return "INVALID"
    order_id = order_id.strip()
    if not order_id:
        return "INVALID"
    prefix = order_id[0].upper()
    if prefix == "T":
        return "T"
    elif prefix == "S":
        return "S"
    return "INVALID"


def validate_orders(order_ids: list[str]) -> tuple[list[str], list[str]]:
    """验证并分类单号列表。

    :return: (valid_orders, invalid_orders)
    """
    valid = []
    invalid = []
    for oid in order_ids:
        oid = oid.strip() if isinstance(oid, str) else str(oid)
        if classify_order(oid) != "INVALID":
            valid.append(oid)
        else:
            invalid.append(oid)
    return valid, invalid
