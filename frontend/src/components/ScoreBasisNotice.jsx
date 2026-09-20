/**
 * 跨班次均分折算口径说明。
 * basis 形如 { comparable_items, rule, included_count, excluded_count }。
 */
export default function ScoreBasisNotice({ basis, compact = false }) {
  if (!basis) return null;
  const items = (basis.comparable_items || []).join('、');
  return (
    <div className="score-basis" title={basis.rule || ''}>
      {compact ? (
        <span className="hint">
          均分按固定可比项折算：{items}（纳入 {basis.included_count ?? 0} 条
          {basis.excluded_count ? `，剔除 ${basis.excluded_count} 条` : ''}）
        </span>
      ) : (
        <>
          <div className="score-basis-title">
            跨班次均分折算口径
            <span className="tag tag-primary" style={{ marginLeft: 8 }}>
              纳入 {basis.included_count ?? 0} 条
            </span>
            {basis.excluded_count ? (
              <span className="tag" style={{ marginLeft: 6 }}>
                剔除 {basis.excluded_count} 条
              </span>
            ) : null}
          </div>
          <div className="muted" style={{ fontSize: 12.5, lineHeight: 1.7 }}>
            {basis.rule}
          </div>
        </>
      )}
    </div>
  );
}
