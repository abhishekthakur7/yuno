import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import RouteView from './RouteView'

describe('RouteView', () => {
  it('renders children and no state main when ready', () => {
    render(
      <RouteView state="ready" label="Reports">
        <div>child content</div>
      </RouteView>,
    )

    expect(screen.getByText('child content')).toBeInTheDocument()
    expect(screen.queryByRole('main')).not.toBeInTheDocument()
  })

  it('renders the failure view with a Retry button that calls onRetry', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()

    render(
      <RouteView state="failure" label="Reports" onRetry={onRetry}>
        <div>child content</div>
      </RouteView>,
    )

    const main = screen.getByRole('main')
    expect(main).toHaveAttribute('data-route-state', 'failure')
    expect(screen.queryByText('child content')).not.toBeInTheDocument()

    const retryButton = screen.getByRole('button', { name: 'Retry' })
    await user.click(retryButton)
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders the loading view with no Retry button', () => {
    render(
      <RouteView state="loading" label="Reports" onRetry={vi.fn()}>
        <div>child content</div>
      </RouteView>,
    )

    const main = screen.getByRole('main')
    expect(main).toHaveAttribute('data-route-state', 'loading')
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
  })
})
