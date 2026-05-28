export function parseMoney(text: string): number {
  const cleaned = text.replace(/[^0-9.\-]/g, '');
  return Number.parseFloat(cleaned);
}

export function formatMoney(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}
