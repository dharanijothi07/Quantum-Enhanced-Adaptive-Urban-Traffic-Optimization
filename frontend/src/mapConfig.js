// Map Provider & API Key Configuration
export const DEFAULT_MAP_API_KEY = "rc_aa67a6ad9f7b854e105e085bfa3c4197e1488db27aaf891fe93ded2ce2accb78";

export const getMapApiKey = (networkKey) => {
  return (
    networkKey ||
    (typeof import.meta !== 'undefined' && import.meta.env?.VITE_MAP_API_KEY) ||
    DEFAULT_MAP_API_KEY
  );
};
