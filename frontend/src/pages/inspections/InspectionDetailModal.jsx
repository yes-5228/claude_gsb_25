import Modal from '../../components/Modal.jsx';
import DetailList from '../../components/DetailList.jsx';
import { GradeTag, ScorePill, StatusTag } from '../../components/Tags.jsx';
import { useDictionaries } from '../../hooks/useDictionaries.js';
import { formatDateTime } from '../../utils/format.js';

export default function InspectionDetailModal({ inspection, onClose, onReportIssue }) {
  const { dictionaries } = useDictionaries();
  if (!inspection) return null;

  const comparableItems = dictionaries?.comparable_items || [];
  const snapshotItems = inspection.check_items?.length
    ? inspection.check_items
    : (inspection.items || []).map((item) => item.name);

  return (
    <Modal
      title={`巡查详情 - ${inspection.restroom?.name ?? ''}`}
      onClose={onClose}
      width={760}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            关闭
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onReportIssue(inspection)}
          >
            就此记录上报问题
          </button>
        </>
      }
    >
      <DetailList
        items={[
          { label: '巡查时间', value: formatDateTime(inspection.inspect_time) },
          { label: '巡查人', value: inspection.inspector },
          { label: '班次', value: inspection.shift },
          {
            label: '检查项组合',
            value: `提交时快照 v${inspection.check_config_version ?? 1} · ${snapshotItems.length} 项`,
          },
          { label: '得分', value: <ScorePill score={inspection.score} /> },
          { label: '评分等级', value: <GradeTag grade={inspection.grade} /> },
          { label: '巡查结论', value: <StatusTag status={inspection.result} /> },
          { label: '关联问题', value: `${inspection.issue_count} 条` },
          { label: '巡查备注', value: inspection.remark || '无' },
        ]}
      />

      <div className="section-title">
        检查项明细
        <span className="muted" style={{ fontSize: 12, fontWeight: 'normal', marginLeft: 8 }}>
          按提交当时的{inspection.shift}组合展示与算分
        </span>
      </div>
      <div className="check-grid">
        {(inspection.items || []).map((item) => (
          <div className={`check-item${item.score < 6 ? ' is-low' : ''}`} key={item.name}>
            <div className="name">
              {item.name}
              {comparableItems.includes(item.name) ? (
                <span className="tag" style={{ marginLeft: 6, fontSize: 11 }} title="跨班次折算固定可比项">
                  可比
                </span>
              ) : null}
            </div>
            <div className="score-line">
              <ScorePill score={item.score} />
              <span className="muted">{item.score >= 6 ? '达标' : '不达标'}</span>
            </div>
            {item.remark ? <div className="muted" style={{ fontSize: 12 }}>{item.remark}</div> : null}
          </div>
        ))}
      </div>
    </Modal>
  );
}
