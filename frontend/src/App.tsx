import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { BlockedAuthorsPage } from './pages/BlockedAuthorsPage'
import { CampaignPage } from './pages/CampaignPage'
import { CampaignsPage } from './pages/CampaignsPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PostPage } from './pages/PostPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<CampaignsPage />} />
        <Route path="campaigns/:campaignId" element={<CampaignPage />} />
        <Route path="posts/:postId" element={<PostPage />} />
        <Route path="do-not-contact" element={<BlockedAuthorsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
