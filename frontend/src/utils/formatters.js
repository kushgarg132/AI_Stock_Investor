export const formatCurrency = (value, currency = 'USD') => {
  if (value === null || value === undefined || isNaN(value)) return '---';
  const locale = currency === 'INR' ? 'en-IN' : 'en-US';
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
};

export const formatCompactNumber = (value) => {
    if (value === null || value === undefined || isNaN(value)) return '---';
    return new Intl.NumberFormat('en-US', {
        notation: 'compact',
        maximumFractionDigits: 2
    }).format(value);
};

export const formatPercent = (value) => {
    if (value === null || value === undefined || isNaN(value)) return '---';
    return new Intl.NumberFormat('en-US', {
        style: 'percent',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value / 100);
}
