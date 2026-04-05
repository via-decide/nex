'use client';

import { LeftPanel } from '../components/LeftPanel';
import { CenterPanel } from '../components/CenterPanel';
import { RightPanel } from '../components/RightPanel';

export default function Home() {
  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      overflow: 'hidden',
      background: 'var(--bg-primary)',
    }}>
      <LeftPanel />
      <CenterPanel />
      <RightPanel />
    </div>
  );
}
