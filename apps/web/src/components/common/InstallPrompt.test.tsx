import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { InstallPrompt } from '@/components/common/InstallPrompt';

class BeforeInstallPromptEvent extends Event {
  prompt = vi.fn(async () => undefined);
  userChoice = Promise.resolve({ outcome: 'accepted' as const, platform: 'web' });
}

describe('install suggestion', () => {
  it('waits for a real install event, then asks only after the shopper taps', async () => {
    render(<InstallPrompt />);
    expect(screen.queryByRole('complementary', { name: 'Install Tripat Pansari' })).toBeNull();

    const installEvent = new BeforeInstallPromptEvent('beforeinstallprompt', {
      cancelable: true,
    });
    const preventDefault = vi.spyOn(installEvent, 'preventDefault');
    await act(async () => {
      window.dispatchEvent(installEvent);
    });

    expect(preventDefault).toHaveBeenCalledOnce();
    const installButton = await screen.findByRole('button', { name: 'Install' });
    expect(installEvent.prompt).not.toHaveBeenCalled();

    fireEvent.click(installButton);
    await waitFor(() => expect(installEvent.prompt).toHaveBeenCalledOnce());
    await waitFor(() => {
      expect(screen.queryByRole('complementary', { name: 'Install Tripat Pansari' })).toBeNull();
    });
  });

  it('explains the manual Add to Home Screen path on iOS', () => {
    const descriptor = Object.getOwnPropertyDescriptor(navigator, 'userAgent');
    Object.defineProperty(navigator, 'userAgent', {
      configurable: true,
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)',
    });
    try {
      render(<InstallPrompt />);
      expect(screen.getByText(/Tap Share, then “Add to Home Screen”/)).toBeInTheDocument();
    } finally {
      if (descriptor) Object.defineProperty(navigator, 'userAgent', descriptor);
    }
  });

  it('lets the shopper dismiss the non-modal suggestion', async () => {
    render(<InstallPrompt />);
    const installEvent = new BeforeInstallPromptEvent('beforeinstallprompt', {
      cancelable: true,
    });
    await act(async () => {
      window.dispatchEvent(installEvent);
    });
    const aside = await screen.findByRole('complementary', { name: 'Install Tripat Pansari' });
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss install suggestion' }));
    await waitFor(() => expect(aside).not.toBeInTheDocument());
  });
});
