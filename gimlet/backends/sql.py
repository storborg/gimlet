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
        table = self.table
        key_col = table.c.key
        raw = self.serialize(value)
        # Check if this key exists with a SELECT FOR UPDATE, to protect
        # against a race with other concurrent writers of this key.
        r = table.count(key_col == key, for_update=True).scalar()
        if r:
            # If it exists, use an UPDATE.
            table.update().values(data=raw).where(key_col == key).execute()
        else:
            # Otherwise INSERT.
            table.insert().values(key=key, data=raw).execute()

    def __getitem__(self, key):
        raw = select([self.table.c.data], self.table.c.key == key).scalar()
        if raw:
            return self.deserialize(raw)
        else:
            raise KeyError('key %r not found' % key)
