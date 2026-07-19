import unittest
from app.core.config_migrations import migrate
class ConfigMigrationTests(unittest.TestCase):
 def test_sequential_migration(self):
  data,steps=migrate({"schema_version":1,"log_level":"DEBUG"});self.assertEqual(steps,(2,3));self.assertEqual(data["privacy"]["log_level"],"DEBUG")
if __name__=="__main__":unittest.main()
