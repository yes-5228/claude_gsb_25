import { useEffect, useState } from 'react';

import { metaApi } from '../api/meta.js';
import { useAsync } from './useAsync.js';

let cache = null;
let cacheVersion = 0;
const CHANGE_EVENT = 'dictionaries-changed';

/** 字典默认只拉取一次并模块级缓存；失效后所有挂载处会自动重新拉取。 */
export function useDictionaries() {
  const [version, setVersion] = useState(cacheVersion);

  useEffect(() => {
    const sync = () => setVersion(cacheVersion);
    window.addEventListener(CHANGE_EVENT, sync);
    return () => window.removeEventListener(CHANGE_EVENT, sync);
  }, []);

  const { data, loading, error } = useAsync(
    async () => {
      if (!cache) cache = await metaApi.dictionaries();
      return cache;
    },
    [version],
  );

  return {
    dictionaries: data ?? cache,
    loading: loading && !cache,
    error,
  };
}

/** 清除字典缓存并通知页面重新拉取（班次组合调整后调用）。 */
export function clearDictionaryCache() {
  cache = null;
  cacheVersion += 1;
  window.dispatchEvent(new Event(CHANGE_EVENT));
}
