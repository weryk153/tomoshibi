import { useCallback, useRef, useState } from 'react';

export function useLocalStorage<T>(
  key: string,
  initialValue: T,
  options?: {
    filter?: (value: T) => T
  },
) {
  const filterRef = useRef(options?.filter);
  filterRef.current = options?.filter;
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      const parsedValue = item ? JSON.parse(item) : initialValue;
      return parsedValue;
    } catch (error) {
      console.error(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  });

  const setValue = useCallback((value: T | ((val: T) => T)) => {
    setStoredValue((current) => {
      try {
        const valueToStore = value instanceof Function ? value(current) : value;
        const filteredValue = filterRef.current
          ? filterRef.current(valueToStore)
          : valueToStore;
        window.localStorage.setItem(key, JSON.stringify(filteredValue));
        return valueToStore;
      } catch (error) {
        console.error(`Error setting localStorage key "${key}":`, error);
        return current;
      }
    });
  }, [key]);

  return [storedValue, setValue] as const;
}
