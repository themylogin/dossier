import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChatTabs, chatsOfTab, visibleTabs } from './ChatTabs';

const downloaded = { id: 1, name: 'Alice', state: { downloaded: true } };
const downloading = { id: 2, name: 'Bob', state: { downloaded: false } };
const unreported = { id: 3, name: 'Carol' };

describe('ChatTabs', () => {
  it('shows All, Downloaded, and Downloading with their counts while a chat downloads', () => {
    render(<ChatTabs chats={[downloaded, downloading, unreported]} activeTab="all" onSelect={vi.fn()} />);

    expect(screen.getAllByRole('button').map(button => button.textContent)).toEqual([
      'All3',
      'Downloaded1',
      'Downloading2'
    ]);
  });

  it('hides Downloading when every chat is downloaded', () => {
    expect(visibleTabs([downloaded]).map(tab => tab.id)).toEqual(['all', 'downloaded']);
  });

  it('puts each chat into its tab', () => {
    const chats = [downloaded, downloading, unreported];

    expect(chatsOfTab(chats, 'downloaded')).toEqual([downloaded]);
    expect(chatsOfTab(chats, 'downloading')).toEqual([downloading, unreported]);
    expect(chatsOfTab(chats, 'all')).toEqual(chats);
  });

  it('marks the active tab and reports a click', () => {
    const onSelect = vi.fn();
    render(<ChatTabs chats={[downloaded, downloading]} activeTab="downloading" onSelect={onSelect} />);

    fireEvent.click(screen.getByRole('button', { name: /^Downloaded/ }));

    expect(screen.getByRole('button', { name: /^Downloading/ })).toHaveClass('tab-active');
    expect(onSelect).toHaveBeenCalledWith('downloaded');
  });
});
