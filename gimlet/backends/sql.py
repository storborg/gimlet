from sqlalchemy import MetaData, Table, Column, types, create_engine, select

from .base import BaseBackend


class SQLBackend(BaseBackend):

    def __init__(self, url, table_name='gimlet_channels', **engine_kwargs):
        meta = MetaData(bind=create_engine(url, **engine_kwargs))
        self.table = Table(table_name, meta,
                           Column('id', types.Integer, primary_key=True),
                           Column('key', types.CHAR(32), nullable=False,
                                  unique=True),
                           Column('data', types.LargeBinary, nullable=False))
        self.table.create(checkfirst=True)

    def __setitem__(self, key, value):
        raw = self.serialize(value)

        # Check if this key exists with a SELECT FOR UPDATE, to protect
        # against a race with other concurrent writers of this key.
        r = self.table.select('1', for_update=True).\
            where(self.table.c.key == key).execute().fetchone()

        if r:
            # If it exists, use an UPDATE.
            self.table.update().values(data=raw).\
                where(self.table.c.key == key).execute()
        else:
            # Otherwise INSERT.
            self.table.insert().values(key=key, data=raw).execute()

    def __getitem__(self, key):
        r = select([self.table.c.data], self.table.c.key == key).\
            execute().fetchone()
        if r:
            raw = r[0]
            return self.deserialize(raw)
        else:
            raise KeyError('key %r not found' % key)
