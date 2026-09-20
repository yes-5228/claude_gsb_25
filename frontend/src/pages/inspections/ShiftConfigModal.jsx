import { useEffect, useMemo, useState } from 'react';

import { shiftConfigApi } from '../../api/shiftConfigs.js';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useDictionaries } from '../../hooks/useDictionaries.js';

/**
 * 班次检查项组合配置。
 * 调整只对保存之后新提交的巡查生效；历史巡查仍按提交当时的组合展示与算分。
 */
export default function ShiftConfigModal({ onClose, onSaved }) {
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const [drafts, setDrafts] = useState({}); // { [shift]: string[] }
  const [savingShift, setSavingShift] = useState(null);
  const [error, setError] = useState(null);

  const configs = useMemo(() => dictionaries?.shift_check_items || [], [dictionaries]);
  const itemPool = dictionaries?.inspection_check_items || [];
  const comparableItems = dictionaries?.comparable_items || [];

  useEffect(() => {
    setDrafts(Object.fromEntries(configs.map((c) => [c.shift, [...c.check_items]])));
  }, [dictionaries]);

  const toggle = (shift, name) => {
    setDrafts((prev) => {
      const current = prev[shift] || [];
      const next = current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name];
      return { ...prev, [shift]: next };
    });
  };

  const saveShift = async (config) => {
    const next = drafts[config.shift] || [];
    if (!next.length) {
      setError(`${config.shift}至少保留 1 个检查项`);
      return;
    }
    setSavingShift(config.shift);
    setError(null);
    try {
      const updated = await shiftConfigApi.update(config.shift, {
        check_items: itemPool.filter((name) => next.includes(name)),
        remark: '页面配置调整',
      });
      toast.success(`${config.shift}组合已调整为 v${updated.version}，仅对之后提交的巡查生效`);
      onSaved?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingShift(null);
    }
  };

  return (
    <Modal
      title="班次检查项组合配置"
      onClose={onClose}
      width={920}
      footer={
        <button type="button" className="btn" onClick={onClose}>
          关闭
        </button>
      }
    >
      <div className="alert" style={{ marginBottom: 12 }}>
        组合调整<strong>只对保存之后新提交的巡查生效</strong>；历史记录仍按提交当时的组合展示与算分，不会被回改。
      </div>
      {error ? <div className="alert alert-error">{error}</div> : null}

      <div className="shift-config-grid">
        {configs.map((config) => {
          const chosen = drafts[config.shift] || [];
          const unchanged =
            chosen.length === config.check_items.length &&
            chosen.every((name, i) => name === config.check_items[i]);
          const missingComparable = comparableItems.filter((name) => !chosen.includes(name));
          return (
            <section className="card" key={config.shift} style={{ marginBottom: 12 }}>
              <div className="card-title">
                <h3>
                  {config.shift}
                  <span className="tag tag-primary" style={{ marginLeft: 8 }}>
                    当前 v{config.version} · {config.check_items.length} 项
                  </span>
                </h3>
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  disabled={unchanged || savingShift === config.shift}
                  onClick={() => saveShift(config)}
                >
                  {savingShift === config.shift ? '保存中…' : '保存该班次'}
                </button>
              </div>
              <div className="check-config-list">
                {itemPool.map((name) => {
                  const checked = chosen.includes(name);
                  const isComparable = comparableItems.includes(name);
                  return (
                    <label
                      key={name}
                      className={`check-config-item${checked ? ' is-on' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(config.shift, name)}
                      />
                      <span>{name}</span>
                      {isComparable ? (
                        <span className="tag" title="跨班次折算固定使用的可比项目">
                          可比项
                        </span>
                      ) : null}
                    </label>
                  );
                })}
              </div>
              {missingComparable.length ? (
                <div className="alert alert-error" style={{ marginTop: 8 }}>
                  该组合缺少固定可比项：{missingComparable.join('、')}。之后该班次的记录将不参与跨班次均分折算。
                </div>
              ) : (
                <div className="muted" style={{ marginTop: 8, fontSize: 12.5 }}>
                  已覆盖全部 {comparableItems.length} 个固定可比项，记录可正常参与跨班次均分。
                </div>
              )}
            </section>
          );
        })}
      </div>
    </Modal>
  );
}
