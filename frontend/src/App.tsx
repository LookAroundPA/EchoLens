import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components'
import { CreatorDetailPage } from './creator-detail-page'
import { JobsPage } from './jobs-page-progress'
import { KnowledgePage } from './knowledge-page'
import {
  CreatorsPage,
  DashboardPage,
  NotFoundPage,
} from './pages'
import { SearchPage } from './search-page'
import { VideoDetailPage } from './video-detail-page'
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
        <Route path="/ask" element={<KnowledgePage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  )
}
