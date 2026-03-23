export function groupCatalogItems(items) {
  const grouped = items.reduce((accumulator, item) => {
    if (!accumulator[item.oil_name]) {
      accumulator[item.oil_name] = []
    }

    accumulator[item.oil_name].push(item)
    return accumulator
  }, {})

  return Object.entries(grouped).map(([name, variants]) => ({
    name,
    items: variants.sort((left, right) => left.volume - right.volume),
  }))
}

export function buildProductIndex(groups) {
  return groups.reduce((index, group) => {
    group.items.forEach((item) => {
      index[`${item.oil_name}_${item.volume}`] = item
    })
    return index
  }, {})
}

export function buildCartItems(quantities) {
  return Object.values(quantities)
}

export function calculateCartTotal(items, productIndex) {
  return items.reduce((total, item) => {
    const product = productIndex[`${item.oilName}_${item.volume}`]
    return total + (product?.price || 0) * item.quantity
  }, 0)
}
