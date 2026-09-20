import { useEffect, useState } from 'react';

import { metaApi } from '../../api/meta.js';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';
import { clearDictionaryCache, useDictionaries } from '../../hooks/useDictionaries.js';

/** 班次检查项组合设置：调整生成新版本，只对之后的录入生效。 */
export default function ChecklistSettingsModal({ onClose, onSaved }) {
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const [checklists, setChecklists] = useState([]);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    metaApi
      .checklists()
      .then((rows) => {
        setChecklists(rows);
        const next = {};
        rows.forEach((row) => {
          next[row.shift] = [...row.items];
        });
        setDraft(next);
      })
      .catch((err) => setError(err.message));
  }, []);

  const toggle = (shift, name) => {
    setDraft((prev) => {
      const selected = new Set(prev[shift] || []);
      if (selected.has(name)) {
        selected.delete(name);
      } else {
        selected.add(name);
      }
      // 始终按检查项池的顺序保存，保证组合内容稳定
      const ordered = (dictionaries?.inspection_check_items || []).filter((item) =>
        selected.has(item),
      );
      return { ...prev, [shift]: ordered };
    });
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      for (const row of checklists) {
        const items = draft[row.shift] || [];
        if (!items.length) {
          throw new Error(`${row.shift}的组合至少保留 1 个检查项`);
        }
        if (items.join('') !== row.items.join('')) {
          await metaApi.updateChecklist(row.shift, items);
        }
      }
      clearDictionaryCache();
      toast.success('检查项组合已更新，新组合对之后的录入生效');
      onSaved?.();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title="班次检查项组合"
      onClose={onClose}
      width={760}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn btn-primary" onClick={save} disabled={saving}>
            {saving ? '保存中…' : '保存组合'}
          </button>
        </>
      }
    >
      <div className="alert alert-info">
        组合调整只对之后录入的巡查生效；历史记录仍按提交当时的组合展示与算分。
      </div>
      {error ? <div className="alert alert-error">{error}</div> : null}
      {checklists.map((row) => (
        <section key={row.shift} style={{ marginBottom: 16 }}>
          <div className="card-title">
            <h3>{row.shift}</h3>
            <span className="hint">
              当前 v{row.version} · 已选 {(draft[row.shift] || []).length} 项
            </span>
          </div>
          <div className="check-grid">
            {(dictionaries?.inspection_check_items || []).map((name) => {
              const checked = (draft[row.shift] || []).includes(name);
              return (
                <label
                  key={name}
                  className="check-item"
                  style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(row.shift, name)}
                  />
                  <span className="name">{name}</span>
                </label>
              );
            })}
          </div>
        </section>
      ))}
    </Modal>
  );
}
