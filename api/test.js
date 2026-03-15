export default function handler(req, res) {
  res.status(200).json({ 
    message: "测试成功！",
    time: new Date().toLocaleString()
  })
}
