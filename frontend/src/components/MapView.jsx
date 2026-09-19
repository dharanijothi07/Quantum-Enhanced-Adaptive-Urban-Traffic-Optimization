import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix default Leaflet icon paths
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'
});

// Custom animated ambulance icon
const ambulanceIcon = L.divIcon({
  className: 'custom-ambulance-icon',
  html: `<div style="
    display: flex; align-items: center; justify-content: center;
    width: 32px; height: 32px; background: #ef4444; border: 2px solid white;
    border-radius: 50%; box-shadow: 0 0 15px rgba(239, 68, 68, 0.9);
    animation: bounce 0.8s infinite alternate; font-size: 16px;">
    🚑
  </div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16]
});

function MapRecenter({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center) map.setView(center, 15);
  }, [center, map]);
  return null;
}

export default function MapView({ network, state }) {
  const mapCenter = network?.map_center || [12.9716, 77.5946];
  const intersections = network?.intersections || {};
  const links = network?.links || {};

  const signals = state?.signals || {};
  const linkStates = state?.links || {};
  const corridorActive = state?.corridor_active || [];
  const ambulance = state?.ambulance || {};
  const optimizedPlan = state?.optimized_plan || {};

  // Compute color based on link density / status
  const getLinkColor = (linkId, linkMeta) => {
    const lState = linkStates[linkId];
    if (!lState) return '#64748b';
    if (lState.blocked) return '#475569'; // Dark gray when blocked
    const density = lState.density || 0;
    if (density >= 0.75) return '#ef4444'; // Red
    if (density >= 0.40) return '#f59e0b'; // Amber
    return '#10b981'; // Green
  };

  return (
    <div className="relative w-full h-[520px] rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-2xl">
      <MapContainer
        center={mapCenter}
        zoom={15}
        scrollWheelZoom={false}
        className="w-full h-full"
        style={{ background: '#090d16' }}
      >
        <MapRecenter center={mapCenter} />

        {/* Dark Mode OSM Tiles */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          maxZoom={19}
        />

        {/* 1. Road Links Polylines */}
        {Object.entries(links).map(([linkId, linkMeta]) => {
          if (!linkMeta.geometry || linkMeta.geometry.length < 2) return null;
          const lState = linkStates[linkId];
          const color = getLinkColor(linkId, linkMeta);
          const isBlocked = lState?.blocked;
          const queue = lState?.queue || 0;
          const capacity = lState?.capacity || 30;

          return (
            <Polyline
              key={linkId}
              positions={linkMeta.geometry}
              pathOptions={{
                color: color,
                weight: isBlocked ? 3 : 5,
                opacity: isBlocked ? 0.6 : 0.85,
                dashArray: isBlocked ? '6, 6' : undefined
              }}
            >
              <Tooltip sticky>
                <div className="text-xs font-mono bg-slate-900 text-white p-1 rounded border border-slate-700">
                  <div className="font-bold text-cyan-400">{linkId}</div>
                  <div>Queue: {queue} / {capacity}</div>
                  <div>In-Transit: {lState?.in_transit || 0}</div>
                  {isBlocked && <div className="text-rose-400 font-bold">BLOCKED / ACCIDENT</div>}
                </div>
              </Tooltip>
            </Polyline>
          );
        })}

        {/* 2. Active Ambulance Route Polyline Glow */}
        {ambulance.active && ambulance.route && (
          <Polyline
            positions={ambulance.route.map((nodeId) => [
              intersections[nodeId]?.lat || 0,
              intersections[nodeId]?.lon || 0
            ]).filter(([lat]) => lat !== 0)}
            pathOptions={{
              color: '#38bdf8',
              weight: 4,
              dashArray: '4, 8',
              opacity: 0.9
            }}
          />
        )}

        {/* 3. Intersections Nodes */}
        {Object.entries(intersections).map(([nodeId, inter]) => {
          const sig = signals[nodeId];
          const isEW = sig?.phase === 1; // 0 = NS (Green), 1 = EW (Blue)
          const inLostTime = sig?.lost_time;
          const isCorridor = corridorActive.includes(nodeId);
          const plan = optimizedPlan[nodeId] || [sig?.phase || 0];

          // Format plan string e.g. "NS -> EW -> EW"
          const planText = plan.map((p) => (p === 0 ? 'NS' : 'EW')).join(' → ');

          let fillColor = isEW ? '#3b82f6' : '#10b981'; // Blue vs Green
          let strokeColor = '#ffffff';

          if (inLostTime) {
            strokeColor = '#eab308'; // Amber border on lost time
          }
          if (isCorridor) {
            strokeColor = '#ec4899'; // Pink/cyan pulse on active corridor
          }

          return (
            <CircleMarker
              key={nodeId}
              center={[inter.lat, inter.lon]}
              radius={isCorridor ? 15 : 12}
              pathOptions={{
                fillColor: fillColor,
                fillOpacity: 0.9,
                color: strokeColor,
                weight: isCorridor ? 4 : inLostTime ? 3 : 2
              }}
            >
              <Tooltip direction="top" offset={[0, -10]} permanent opacity={0.95}>
                <div className="bg-slate-900/90 text-slate-100 font-sans p-1 rounded-md border border-slate-700 text-center shadow-lg pointer-events-none">
                  <div className="font-extrabold text-xs flex items-center justify-center gap-1">
                    <span className={isCorridor ? 'text-pink-400 font-bold animate-pulse' : 'text-cyan-300'}>
                      {nodeId}
                    </span>
                    <span className={`px-1 rounded text-[10px] ${isEW ? 'bg-blue-950 text-blue-300' : 'bg-emerald-950 text-emerald-300'}`}>
                      {inLostTime ? 'TRANSITION' : isEW ? 'EW GREEN' : 'NS GREEN'}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                    Plan: <span className="text-slate-200">{planText}</span>
                  </div>
                </div>
              </Tooltip>
            </CircleMarker>
          );
        })}

        {/* 4. Ambulance Animated Marker */}
        {ambulance.active && ambulance.pos && (
          <Marker position={ambulance.pos} icon={ambulanceIcon}>
            <Popup>
              <div className="text-xs font-mono p-1">
                <div className="font-bold text-rose-500">🚑 Priority Ambulance</div>
                <div>Elapsed: {ambulance.elapsed}s</div>
                <div>Stops: {ambulance.total_stops}</div>
                <div>Route: {ambulance.route?.join(' → ')}</div>
              </div>
            </Popup>
          </Marker>
        )}
      </MapContainer>

      {/* Map Legend & Overlay Badges */}
      <div className="absolute bottom-3 left-3 z-[1000] bg-slate-900/85 backdrop-blur border border-slate-700/80 rounded-xl p-2.5 text-[11px] text-slate-200 flex flex-wrap items-center gap-4 shadow-xl">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block"></span>
          <span>NS Green</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-blue-500 inline-block"></span>
          <span>EW Green</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full border-2 border-amber-400 inline-block"></span>
          <span>Lost Time (3s)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full border-2 border-pink-500 animate-ping inline-block"></span>
          <span>Emergency Corridor</span>
        </div>
        <div className="flex items-center gap-1.5 border-l border-slate-700 pl-3">
          <span className="w-3 h-1 bg-emerald-500 inline-block"></span>
          <span>Free</span>
          <span className="w-3 h-1 bg-amber-500 inline-block"></span>
          <span>Busy</span>
          <span className="w-3 h-1 bg-rose-500 inline-block"></span>
          <span>Queue Surge</span>
        </div>
      </div>
    </div>
  );
}
