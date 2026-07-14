import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components'
import { JobsPage } from './jobs-page'
import {
  CreatorDetailPage,
  CreatorsPage,
  DashboardPage,
  NotFoundPage,
  SearchPage,
  VideoDetailPage,
} from './pages'
import { VideosPage } from './videos-page'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/videos" element={<VideosPage />} />
        <Route path="/videos/:id" element={<VideoDetailPage />} />
        <Route path="/creators" element={<CreatorsPage />} />
        <Route path="/creators/:secUid" element={<CreatorDetailPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  )
}
